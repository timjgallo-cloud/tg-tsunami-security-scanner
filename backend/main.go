package main

import (
	"context"
	"encoding/json"
	"log"
	"os"

	"github.com/gofiber/fiber/v2"
	"github.com/google/tsunami-security-scanner/backend/enrichment"
	"github.com/google/tsunami-security-scanner/backend/gcp"
)

func main() {
	app := fiber.New(fiber.Config{
		AppName: "Tsunami Security Scanner Go Backend",
	})

	ctx := context.Background()
	gcpClient, err := gcp.NewClient(ctx)
	if err != nil {
		log.Fatalf("Failed to initialize GCP client: %v", err)
	}

	// Serve Static Frontend SPA
	app.Static("/", "./frontend/dist")

	api := app.Group("/api/v1")

	api.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok"})
	})

	api.Post("/scan", func(c *fiber.Ctx) error {
		var req struct {
			Target string `json:"target"`
		}
		if err := c.BodyParser(&req); err != nil || req.Target == "" {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid target"})
		}

		execID, err := gcpClient.RunJob(ctx, req.Target)
		if err != nil {
			log.Printf("RunJob error: %v\n", err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": err.Error()})
		}

		return c.JSON(fiber.Map{
			"status":       "started",
			"execution_id": execID,
			"target":       req.Target,
		})
	})

	api.Post("/worker/enrich", func(c *fiber.Ctx) error {
		// Pub/Sub push webhook payload
		var payload struct {
			Message struct {
				Data []byte `json:"data"`
			} `json:"message"`
		}
		if err := c.BodyParser(&payload); err != nil {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid pubsub payload"})
		}

		var msg struct {
			ExecutionID string `json:"execution_id"`
		}
		if err := json.Unmarshal(payload.Message.Data, &msg); err != nil || msg.ExecutionID == "" {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "missing execution_id"})
		}

		log.Printf("[WORKER] Starting background enrichment for execution %s\n", msg.ExecutionID)

		data, err := gcpClient.ReadResults(ctx, msg.ExecutionID+".json")
		if err != nil {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"error": "results not found"})
		}

		enricher := enrichment.NewEnricher()
		enrichedData, err := enricher.EnrichVulnerabilities(ctx, data)
		if err != nil {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": err.Error()})
		}

		if err := gcpClient.WriteResults(ctx, msg.ExecutionID+"_enriched.json", enrichedData); err != nil {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": err.Error()})
		}

		log.Printf("[WORKER] Successfully completed enrichment for %s\n", msg.ExecutionID)
		return c.JSON(fiber.Map{"status": "completed", "execution_id": msg.ExecutionID})
	})

	api.Get("/results/:execution_id", func(c *fiber.Ctx) error {
		execID := c.Params("execution_id")

		// Check if pre-enriched exists
		data, err := gcpClient.ReadResults(ctx, execID+"_enriched.json")
		if err == nil {
			return c.JSON(fiber.Map{"data": data, "enriched": true})
		}

		// Fallback to raw
		data, err = gcpClient.ReadResults(ctx, execID+".json")
		if err != nil {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"error": "results not ready or not found"})
		}

		return c.JSON(fiber.Map{"data": data, "enriched": false})
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Fatal(app.Listen(":" + port))
}
