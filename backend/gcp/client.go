package gcp

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"

	"cloud.google.com/go/pubsub"
	run "cloud.google.com/go/run/apiv2"
	"cloud.google.com/go/run/apiv2/runpb"
	"cloud.google.com/go/storage"
	"github.com/google/uuid"
)

type Client struct {
	ProjectID  string
	Region     string
	JobName    string
	BucketName string
	TopicName  string
	LocalMode  bool

	storageClient *storage.Client
	runClient     *run.JobsClient
	pubsubClient  *pubsub.Client
}

func NewClient(ctx context.Context) (*Client, error) {
	c := &Client{
		ProjectID:  os.Getenv("PROJECT_ID"),
		Region:     os.Getenv("REGION"),
		JobName:    os.Getenv("SCANNER_JOB_NAME"),
		BucketName: os.Getenv("GCS_BUCKET"),
		TopicName:  os.Getenv("PUBSUB_TOPIC"),
		LocalMode:  os.Getenv("LOCAL_MODE") == "true",
	}

	if c.Region == "" {
		c.Region = "us-central1"
	}
	if c.TopicName == "" {
		c.TopicName = "tsunami-scan-completed"
	}

	if c.LocalMode {
		log.Println("[MOCK] Running in LOCAL_MODE. Using mock GCP services.")
		return c, nil
	}

	var err error
	c.storageClient, err = storage.NewClient(ctx)
	if err != nil {
		return nil, fmt.Errorf("storage.NewClient: %w", err)
	}

	c.runClient, err = run.NewJobsClient(ctx)
	if err != nil {
		return nil, fmt.Errorf("run.NewJobsClient: %w", err)
	}

	c.pubsubClient, err = pubsub.NewClient(ctx, c.ProjectID)
	if err != nil {
		return nil, fmt.Errorf("pubsub.NewClient: %w", err)
	}

	return c, nil
}

func (c *Client) RunJob(ctx context.Context, target string) (string, error) {
	execID := uuid.New().String()

	if c.LocalMode {
		log.Printf("[MOCK] Triggering job for target %s with ID %s\n", target, execID)
		return execID, nil
	}

	formattedJobName := fmt.Sprintf("projects/%s/locations/%s/jobs/%s", c.ProjectID, c.Region, c.JobName)
	signedURL, err := c.GenerateSignedURL(ctx, execID+".json")
	if err != nil {
		return "", fmt.Errorf("GenerateSignedURL: %w", err)
	}

	req := &runpb.RunJobRequest{
		Name: formattedJobName,
		Overrides: &runpb.RunJobRequest_Overrides{
			ContainerOverrides: []*runpb.RunJobRequest_Overrides_ContainerOverride{
				{
					Env: []*runpb.EnvVar{
						{Name: "TARGET", Value: target},
						{Name: "EXECUTION_ID", Value: execID},
						{Name: "GCS_BUCKET", Value: c.BucketName},
						{Name: "UPLOAD_URL", Value: signedURL},
						{Name: "PUBSUB_TOPIC", Value: c.TopicName},
					},
				},
			},
		},
	}

	_, err = c.runClient.RunJob(ctx, req)
	if err != nil {
		return "", fmt.Errorf("RunJob: %w", err)
	}

	log.Printf("Job triggered for target %s, Execution ID: %s\n", target, execID)
	return execID, nil
}

func (c *Client) GenerateSignedURL(ctx context.Context, filename string) (string, error) {
	if c.LocalMode {
		log.Printf("[MOCK] Generating signed URL for %s\n", filename)
		return fmt.Sprintf("http://localhost:8080/mock-upload/%s", filename), nil
	}

	opts := &storage.SignedURLOptions{
		Scheme:      storage.SigningSchemeV4,
		Method:      "PUT",
		Expires:     time.Now().Add(2 * time.Hour),
		ContentType: "application/json",
	}

	url, err := c.storageClient.Bucket(c.BucketName).SignedURL(filename, opts)
	if err != nil {
		return "", fmt.Errorf("SignedURL: %w", err)
	}
	return url, nil
}

func (c *Client) ReadResults(ctx context.Context, filename string) (map[string]interface{}, error) {
	if c.LocalMode {
		log.Printf("[MOCK] Reading %s from mock storage.\n", filename)
		return map[string]interface{}{
			"scanStatus": "COMPLETED",
			"scanFindings": []interface{}{
				map[string]interface{}{
					"vulnerability": map[string]interface{}{
						"cveId": "CVE-2024-1234",
						"title": "Mock Vulnerability in Go Backend",
						"rating": "HIGH",
					},
				},
			},
		}, nil
	}

	rc, err := c.storageClient.Bucket(c.BucketName).Object(filename).NewReader(ctx)
	if err != nil {
		return nil, fmt.Errorf("Object.NewReader: %w", err)
	}
	defer rc.Close()

	var data map[string]interface{}
	if err := json.NewDecoder(rc).Decode(&data); err != nil {
		return nil, fmt.Errorf("json.Decode: %w", err)
	}
	return data, nil
}

func (c *Client) WriteResults(ctx context.Context, filename string, data map[string]interface{}) error {
	if c.LocalMode {
		log.Printf("[MOCK] Writing %s to mock storage.\n", filename)
		return nil
	}

	wc := c.storageClient.Bucket(c.BucketName).Object(filename).NewWriter(ctx)
	wc.ContentType = "application/json"

	if err := json.NewEncoder(wc).Encode(data); err != nil {
		wc.Close()
		return fmt.Errorf("json.Encode: %w", err)
	}
	return wc.Close()
}
