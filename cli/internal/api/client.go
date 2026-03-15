// Package api provides the BugPilot API client for the CLI.
package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const defaultTimeout = 30 * time.Second

// Client is the BugPilot API client.
type Client struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

// New creates a new API client.
func New(baseURL, apiKey string) *Client {
	return &Client{
		BaseURL: baseURL,
		APIKey:  apiKey,
		HTTPClient: &http.Client{
			Timeout: defaultTimeout,
		},
	}
}

// APIError represents an API error response.
type APIError struct {
	StatusCode int
	Body       string
	Detail     string `json:"detail"`
	Error_     string `json:"error"`
	Message    string `json:"message"`
}

func (e *APIError) Error() string {
	if e.Message != "" {
		return fmt.Sprintf("API error %d: %s", e.StatusCode, e.Message)
	}
	if e.Detail != "" {
		return fmt.Sprintf("API error %d: %s", e.StatusCode, e.Detail)
	}
	return fmt.Sprintf("API error %d: %s", e.StatusCode, e.Body)
}

// Do performs an HTTP request to the API. Exported for use in commands.
func (c *Client) Do(method, path string, body interface{}, out interface{}) error {
	return c.do(method, path, body, out)
}

func (c *Client) do(method, path string, body interface{}, out interface{}) error {
	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("marshal request: %w", err)
		}
		reqBody = bytes.NewReader(b)
	}

	req, err := http.NewRequest(method, c.BaseURL+path, reqBody)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		apiErr := &APIError{StatusCode: resp.StatusCode, Body: string(respBytes)}
		_ = json.Unmarshal(respBytes, apiErr)
		return apiErr
	}

	if out != nil && len(respBytes) > 0 {
		if err := json.Unmarshal(respBytes, out); err != nil {
			return fmt.Errorf("unmarshal response: %w", err)
		}
	}
	return nil
}

// ── Key validation ─────────────────────────────────────────────────────────────

type ValidateKeyRequest struct {
	TermsAccepted   bool   `json:"terms_accepted"`
	TermsVersion    string `json:"terms_version"`
	TermsAcceptedAt string `json:"terms_accepted_at"`
	CLIVersion      string `json:"cli_version"`
	Platform        string `json:"platform"`
}

type ValidateKeyResponse struct {
	Valid   bool   `json:"valid"`
	OrgName string `json:"org_name"`
	OrgID   string `json:"org_id"`
	Plan    string `json:"plan"`
}

func (c *Client) ValidateKey(req ValidateKeyRequest) (*ValidateKeyResponse, error) {
	var resp ValidateKeyResponse
	if err := c.do("GET", "/v1/keys/validate", req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// ── Investigations ─────────────────────────────────────────────────────────────

type CreateInvestigationRequest struct {
	TicketID       string `json:"ticket_id,omitempty"`
	TicketSource   string `json:"ticket_source,omitempty"`
	ServiceName    string `json:"service_name,omitempty"`
	Text           string `json:"text,omitempty"`
	Since          string `json:"since,omitempty"`
	Layer          string `json:"layer"`
	WindowMinutes  int    `json:"window_minutes"`
	SuppressSlack  bool   `json:"suppress_slack,omitempty"`
	DryRun         bool   `json:"dry_run,omitempty"`
}

type CreateInvestigationResponse struct {
	InvestigationID  string `json:"investigation_id"`
	Status           string `json:"status"`
	EstimatedSeconds int    `json:"estimated_seconds"`
}

func (c *Client) CreateInvestigation(req CreateInvestigationRequest) (*CreateInvestigationResponse, error) {
	var resp CreateInvestigationResponse
	if err := c.do("POST", "/v1/investigations", req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

type InvestigationStatus struct {
	InvestigationID string       `json:"investigation_id"`
	Status          string       `json:"status"`
	ElapsedSeconds  int          `json:"elapsed_seconds"`
	Progress        []StepStatus `json:"progress"`
}

type StepStatus struct {
	Step       string  `json:"step"`
	Status     string  `json:"status"`
	DurationMs *int    `json:"duration_ms"`
}

func (c *Client) GetInvestigationStatus(id string) (*InvestigationStatus, error) {
	var resp InvestigationStatus
	if err := c.do("GET", "/v1/investigations/"+id+"/status", nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

type Investigation struct {
	InvestigationID  string       `json:"investigation_id"`
	Status           string       `json:"status"`
	TriggerRef       string       `json:"trigger_ref"`
	TriggerSource    string       `json:"trigger_source"`
	ServiceName      string       `json:"service_name"`
	FailureClass     string       `json:"failure_class"`
	DurationMS       int          `json:"duration_ms"`
	Hypotheses       []Hypothesis `json:"hypotheses"`
	BlastRadius      *BlastRadius `json:"blast_radius,omitempty"`
	ConnectorsUsed   []string     `json:"connectors_used"`
	ConnectorsMissing []string    `json:"connectors_missing"`
	ErrorMessage     string       `json:"error_message,omitempty"`
}

type Hypothesis struct {
	Rank        int     `json:"rank"`
	PRID        *int    `json:"pr_id"`
	PRURL       string  `json:"pr_url"`
	PRTitle     string  `json:"pr_title"`
	PRAuthor    string  `json:"pr_author"`
	PRMergedAt  string  `json:"pr_merged_at"`
	FilePath    string  `json:"file_path"`
	LineNumber  *int    `json:"line_number"`
	DiffType    string  `json:"diff_type"`
	Confidence  float64 `json:"confidence"`
	Narrative   string  `json:"narrative,omitempty"`
}

type BlastRadius struct {
	Count      int     `json:"count"`
	ValueUSD   float64 `json:"value_usd"`
	Cohort     string  `json:"cohort"`
	WindowStart string `json:"window_start"`
	WindowEnd   string `json:"window_end"`
	Status     string  `json:"status"`
}

func (c *Client) GetInvestigation(id string) (*Investigation, error) {
	var resp Investigation
	if err := c.do("GET", "/v1/investigations/"+id, nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

type FeedbackRequest struct {
	Feedback       string `json:"feedback"`
	HypothesisRank int    `json:"hypothesis_rank"`
	Cause          string `json:"cause,omitempty"`
	SubmittedBy    string `json:"submitted_by,omitempty"`
}

func (c *Client) SubmitFeedback(id string, req FeedbackRequest) error {
	return c.do("POST", "/v1/investigations/"+id+"/feedback", req, nil)
}

// ── History ────────────────────────────────────────────────────────────────────

type HistoryResponse struct {
	Total  int                  `json:"total"`
	Limit  int                  `json:"limit"`
	Offset int                  `json:"offset"`
	Items  []HistoryItem        `json:"items"`
}

type HistoryItem struct {
	InvestigationID string  `json:"investigation_id"`
	Status          string  `json:"status"`
	TriggerRef      string  `json:"trigger_ref"`
	TriggerSource   string  `json:"trigger_source"`
	ServiceName     string  `json:"service_name"`
	FailureClass    string  `json:"failure_class"`
	TopConfidence   float64 `json:"top_confidence"`
	TopPRURL        string  `json:"top_pr_url"`
	DurationMS      int     `json:"duration_ms"`
	QueuedAt        string  `json:"queued_at"`
	Feedback        string  `json:"feedback"`
}

func (c *Client) GetHistory(limit, offset int) (*HistoryResponse, error) {
	var resp HistoryResponse
	path := fmt.Sprintf("/v1/history?limit=%d&offset=%d", limit, offset)
	if err := c.do("GET", path, nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// ── Connectors ─────────────────────────────────────────────────────────────────

type ConnectorInfo struct {
	ID              string                 `json:"id"`
	Type            string                 `json:"type"`
	Name            string                 `json:"name"`
	Status          string                 `json:"status"`
	ServiceMap      map[string]interface{} `json:"service_map"`
	LastHealthCheck string                 `json:"last_health_check"`
}

func (c *Client) ListConnectors() ([]ConnectorInfo, error) {
	var resp []ConnectorInfo
	if err := c.do("GET", "/v1/connectors", nil, &resp); err != nil {
		return nil, err
	}
	return resp, nil
}

type AddConnectorRequest struct {
	Name       string                 `json:"name"`
	Config     map[string]interface{} `json:"config"`
	ServiceMap map[string]interface{} `json:"service_map,omitempty"`
	Role       string                 `json:"role,omitempty"`
}

type AddConnectorResponse struct {
	ConnectorID string `json:"connector_id"`
	Status      string `json:"status"`
}

func (c *Client) AddConnector(connType string, req AddConnectorRequest) (*AddConnectorResponse, error) {
	var resp AddConnectorResponse
	if err := c.do("POST", "/v1/connectors/"+connType, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

func (c *Client) DeleteConnector(connType, name string) error {
	return c.do("DELETE", "/v1/connectors/"+connType+"/"+name, nil, nil)
}

func (c *Client) ConnectorHealth(connType, name string) (map[string]interface{}, error) {
	var resp map[string]interface{}
	if err := c.do("GET", "/v1/connectors/"+connType+"/"+name+"/health", nil, &resp); err != nil {
		return nil, err
	}
	return resp, nil
}
