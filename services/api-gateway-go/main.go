package main

import (
	"fmt"
	"log"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/patrickmn/go-cache"
)

var (
	requestCount int64
	errorCount   int64
	cacheStore   *cache.Cache
)

type HealthResponse struct {
	ServiceName string    `json:"service_name"`
	Status      string    `json:"status"`
	Timestamp   time.Time `json:"timestamp"`
	Version     string    `json:"version"`
	Requests    int64     `json:"requests"`
	Errors      int64     `json:"errors"`
}

type QueryRequest struct {
	Query              string            `json:"query"`
	TopK               int               `json:"top_k"`
	RetrievalStrategy  string            `json:"retrieval_strategy"`
	IncludeSources     bool              `json:"include_sources"`
	UserContext        map[string]string `json:"user_context,omitempty"`
}

type QueryResponse struct {
	Query          string   `json:"query"`
	Response       string   `json:"response"`
	Sources        []string `json:"sources"`
	ProcessingTime float64  `json:"processing_time"`
	Status         string   `json:"status"`
}

type Document struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Type  string `json:"type"`
}

type DocumentsResponse struct {
	Documents []Document `json:"documents"`
	Total     int        `json:"total"`
	Status    string     `json:"status"`
}

type Model struct {
	Name   string `json:"name"`
	Type   string `json:"type"`
	Status string `json:"status"`
}

type ModelsResponse struct {
	Models []Model `json:"models"`
	Total  int     `json:"total"`
	Status string  `json:"status"`
}

type UploadResponse struct {
	Message       string  `json:"message"`
	DocumentID    string  `json:"document_id"`
	Status        string  `json:"status"`
	ProcessingTime float64 `json:"processing_time"`
}

type GenerateRequest struct {
	Prompt string `json:"prompt"`
}

type GenerateResponse struct {
	Prompt        string  `json:"prompt"`
	Response      string  `json:"response"`
	Model         string  `json:"model"`
	TokensUsed    int     `json:"tokens_used"`
	ProcessingTime float64 `json:"processing_time"`
	Status        string  `json:"status"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func init() {
	// Initialize cache with 5 minute expiration and 10 minute cleanup
	cacheStore = cache.New(5*time.Minute, 10*time.Minute)
}

func main() {
	// Set Gin mode
	gin.SetMode(gin.ReleaseMode)
	
	// Create router
	r := gin.New()
	
	// Middleware
	r.Use(gin.Recovery())
	r.Use(corsMiddleware())
	r.Use(requestIDMiddleware())
	r.Use(rateLimitMiddleware())
	r.Use(metricsMiddleware())
	
	// Routes
	r.GET("/health", healthHandler)
	r.GET("/metrics", metricsHandler)
	
	// API routes
	r.POST("/query", queryHandler)
	r.GET("/documents", documentsHandler)
	r.POST("/documents/upload", uploadHandler)
	r.GET("/models", modelsHandler)
	r.POST("/generate", generateHandler)
	
	// Start server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}
	
	log.Printf("🚀 Starting RAG API Gateway on port %s", port)
	log.Printf("📊 High-performance Go API Gateway ready for 1000+ users")
	
	if err := r.Run(":" + port); err != nil {
		log.Fatal("Failed to start server:", err)
	}
}

func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Origin, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization")
		
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		
		c.Next()
	}
}

func requestIDMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			requestID = fmt.Sprintf("req-%d", time.Now().UnixNano())
		}
		c.Set("request_id", requestID)
		c.Header("X-Request-ID", requestID)
		c.Next()
	}
}

func rateLimitMiddleware() gin.HandlerFunc {
	// Simple in-memory rate limiter
	type Client struct {
		requests int
		lastTime time.Time
	}
	
	clients := make(map[string]*Client)
	var mutex sync.RWMutex
	
	return func(c *gin.Context) {
		clientIP := c.ClientIP()
		
		mutex.Lock()
		client, exists := clients[clientIP]
		if !exists {
			client = &Client{requests: 0, lastTime: time.Now()}
			clients[clientIP] = client
		}
		
		now := time.Now()
		if now.Sub(client.lastTime) > time.Second {
			client.requests = 0
			client.lastTime = now
		}
		
		client.requests++
		
		// Rate limit: 100 requests per second per IP
		if client.requests > 100 {
			mutex.Unlock()
			c.JSON(429, ErrorResponse{
				Error:   "rate_limit_exceeded",
				Code:    429,
				Message: "Too many requests, please try again later",
			})
			c.Abort()
			return
		}
		
		mutex.Unlock()
		c.Next()
	}
}

func metricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		atomic.AddInt64(&requestCount, 1)
		
		c.Next()
		
		// Check if response was an error
		if c.Writer.Status() >= 400 {
			atomic.AddInt64(&errorCount, 1)
		}
		
		// Log request
		duration := time.Since(start)
		log.Printf("%s %s %d %v %s", 
			c.Request.Method, 
			c.Request.URL.Path, 
			c.Writer.Status(), 
			duration, 
			c.ClientIP())
	}
}

func healthHandler(c *gin.Context) {
	response := HealthResponse{
		ServiceName: "api-gateway-go",
		Status:      "healthy",
		Timestamp:   time.Now(),
		Version:     "2.0.0",
		Requests:    atomic.LoadInt64(&requestCount),
		Errors:      atomic.LoadInt64(&errorCount),
	}
	
	c.JSON(200, response)
}

func metricsHandler(c *gin.Context) {
	requests := atomic.LoadInt64(&requestCount)
	errors := atomic.LoadInt64(&errorCount)
	
	metrics := gin.H{
		"status":          "ok",
		"total_requests":  requests,
		"total_errors":    errors,
		"error_rate":      float64(errors) / float64(requests) * 100,
		"uptime":          time.Since(time.Now()).String(),
		"cache_stats":     cacheStore.Items(),
		"performance":     "high-performance-go-gateway",
	}
	
	c.JSON(200, metrics)
}

func queryHandler(c *gin.Context) {
	var req QueryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, ErrorResponse{
			Error:   "invalid_request",
			Code:    400,
			Message: "Invalid request format",
		})
		return
	}
	
	if req.Query == "" {
		c.JSON(400, ErrorResponse{
			Error:   "missing_query",
			Code:    400,
			Message: "Query is required",
		})
		return
	}
	
	// Check cache first
	cacheKey := fmt.Sprintf("query:%s:%d:%s", req.Query, req.TopK, req.RetrievalStrategy)
	if cached, found := cacheStore.Get(cacheKey); found {
		c.JSON(200, cached)
		return
	}
	
	// Simulate processing
	start := time.Now()
	
	// Mock response for testing
	response := QueryResponse{
		Query:          req.Query,
		Response:       fmt.Sprintf("This is a high-performance Go response for: %s", req.Query),
		Sources:        []string{"go_source_1", "go_source_2", "go_source_3"},
		ProcessingTime: time.Since(start).Seconds(),
		Status:         "success",
	}
	
	// Cache response
	cacheStore.Set(cacheKey, response, cache.DefaultExpiration)
	
	c.JSON(200, response)
}

func documentsHandler(c *gin.Context) {
	// Check cache
	cacheKey := "documents:list"
	if cached, found := cacheStore.Get(cacheKey); found {
		c.JSON(200, cached)
		return
	}
	
	// Mock response
	response := DocumentsResponse{
		Documents: []Document{
			{ID: "1", Title: "Go Performance Guide", Type: "pdf"},
			{ID: "2", Title: "High-Performance APIs", Type: "txt"},
			{ID: "3", Title: "Go Microservices", Type: "doc"},
			{ID: "4", Title: "RAG System Architecture", Type: "pdf"},
		},
		Total:  4,
		Status: "success",
	}
	
	// Cache response
	cacheStore.Set(cacheKey, response, cache.DefaultExpiration)
	
	c.JSON(200, response)
}

func uploadHandler(c *gin.Context) {
	start := time.Now()
	
	// Mock upload processing
	documentID := fmt.Sprintf("go_doc_%d", time.Now().UnixNano())
	
	response := UploadResponse{
		Message:        "Document uploaded successfully to Go API Gateway",
		DocumentID:     documentID,
		Status:         "uploaded",
		ProcessingTime: time.Since(start).Seconds(),
	}
	
	c.JSON(200, response)
}

func modelsHandler(c *gin.Context) {
	// Check cache
	cacheKey := "models:list"
	if cached, found := cacheStore.Get(cacheKey); found {
		c.JSON(200, cached)
		return
	}
	
	// Mock response
	response := ModelsResponse{
		Models: []Model{
			{Name: "gpt-4-turbo", Type: "llm", Status: "available"},
			{Name: "text-embedding-3-large", Type: "embedding", Status: "available"},
			{Name: "claude-3-opus", Type: "llm", Status: "available"},
			{Name: "gemini-pro", Type: "llm", Status: "available"},
		},
		Total:  4,
		Status: "success",
	}
	
	// Cache response
	cacheStore.Set(cacheKey, response, cache.DefaultExpiration)
	
	c.JSON(200, response)
}

func generateHandler(c *gin.Context) {
	var req GenerateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, ErrorResponse{
			Error:   "invalid_request",
			Code:    400,
			Message: "Invalid request format",
		})
		return
	}
	
	if req.Prompt == "" {
		c.JSON(400, ErrorResponse{
			Error:   "missing_prompt",
			Code:    400,
			Message: "Prompt is required",
		})
		return
	}
	
	// Check cache
	cacheKey := fmt.Sprintf("generate:%s", req.Prompt)
	if cached, found := cacheStore.Get(cacheKey); found {
		c.JSON(200, cached)
		return
	}
	
	// Simulate processing
	start := time.Now()
	
	response := GenerateResponse{
		Prompt:         req.Prompt,
		Response:       fmt.Sprintf("High-performance Go generated response for: %s", req.Prompt),
		Model:          "go-gpt-4-turbo",
		TokensUsed:     150,
		ProcessingTime: time.Since(start).Seconds(),
		Status:         "success",
	}
	
	// Cache response
	cacheStore.Set(cacheKey, response, cache.DefaultExpiration)
	
	c.JSON(200, response)
}
