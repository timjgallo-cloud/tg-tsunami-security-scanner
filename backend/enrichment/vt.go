package enrichment

import (
	"context"
	"log"
	"os"
	"sync"
	"time"
)

var (
	cveCache = make(map[string]float64)
	cacheMu  sync.RWMutex
)

type GtiEnricher struct {
	apiKey string
}

func NewEnricher() *GtiEnricher {
	return &GtiEnricher{
		apiKey: os.Getenv("VT_API_KEY"),
	}
}

func (e *GtiEnricher) EnrichVulnerabilities(ctx context.Context, results map[string]interface{}) (map[string]interface{}, error) {
	if e.apiKey == "" {
		log.Println("VT_API_KEY not set. Skipping enrichment.")
		return results, nil
	}

	findings, ok := results["scanFindings"].([]interface{})
	if !ok {
		return results, nil
	}

	for _, item := range findings {
		finding, ok := item.(map[string]interface{})
		if !ok {
			continue
		}

		vuln, ok := finding["vulnerability"].(map[string]interface{})
		if !ok {
			continue
		}

		cveID, ok := vuln["cveId"].(string)
		if !ok || cveID == "" {
			continue
		}

		score, err := e.GetRiskScore(ctx, cveID)
		if err != nil {
			log.Printf("Failed to enrich %s: %v\n", cveID, err)
			continue
		}
		vuln["gtiRiskScore"] = score
	}

	return results, nil
}

func (e *GtiEnricher) GetRiskScore(ctx context.Context, cveID string) (float64, error) {
	cacheMu.RLock()
	score, exists := cveCache[cveID]
	cacheMu.RUnlock()

	if exists {
		log.Printf("[CACHE HIT] Pulling risk score for %s from cache.\n", cveID)
		return score, nil
	}

	log.Printf("[CACHE MISS] Querying VirusTotal/GTI API for %s...\n", cveID)
	// Mock simulation of VT API call
	time.Sleep(100 * time.Millisecond)
	score = 9.5

	cacheMu.Lock()
	cveCache[cveID] = score
	cacheMu.Unlock()

	return score, nil
}
