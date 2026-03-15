package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"github.com/skonlabs/bugpilot/internal/api"
	"github.com/skonlabs/bugpilot/internal/config"
)

var investigateCmd = &cobra.Command{
	Use:   "investigate [ticket-id|description]",
	Short: "Investigate a bug and identify the root cause PR",
	Long: `Run an investigation to trace a functional bug to the specific PR that introduced it.

Examples:
  bugpilot investigate PROJ-1234
  bugpilot investigate "payments are failing for EU customers"
  bugpilot investigate --service payments --since 2h
  bugpilot investigate --dry-run PROJ-1234`,
	Args: cobra.MaximumNArgs(1),
	RunE: runInvestigate,
}

func init() {
	rootCmd.AddCommand(investigateCmd)
	investigateCmd.Flags().StringP("service", "s", "", "Service name to investigate")
	investigateCmd.Flags().String("since", "", "Start of investigation window (2h, 30m, ISO8601)")
	investigateCmd.Flags().Int("window", 30, "Investigation window in minutes")
	investigateCmd.Flags().String("source", "", "Ticket source (jira|freshdesk|sentry|slack|cli)")
	investigateCmd.Flags().Bool("no-slack", false, "Suppress Slack notification")
	investigateCmd.Flags().Bool("dry-run", false, "Show what would be investigated without running")
	investigateCmd.Flags().Bool("watch", false, "Watch progress in real-time (default: true)")
}

func runInvestigate(cmd *cobra.Command, args []string) error {
	apiKey, err := config.LoadAPIKey()
	if err != nil || apiKey == "" {
		return fmt.Errorf("not configured: run 'bugpilot init' first")
	}

	cfg, _ := config.Load()
	client := api.New(cfg.BaseURL, apiKey)

	// Build request
	req := api.CreateInvestigationRequest{
		Layer:         "l2",
		WindowMinutes: 30,
	}

	if service, _ := cmd.Flags().GetString("service"); service != "" {
		req.ServiceName = service
	}
	if since, _ := cmd.Flags().GetString("since"); since != "" {
		req.Since = since
	}
	if window, _ := cmd.Flags().GetInt("window"); window > 0 {
		req.WindowMinutes = window
	}
	if source, _ := cmd.Flags().GetString("source"); source != "" {
		req.TicketSource = source
	}
	if noSlack, _ := cmd.Flags().GetBool("no-slack"); noSlack {
		req.SuppressSlack = true
	}
	if dryRun, _ := cmd.Flags().GetBool("dry-run"); dryRun {
		req.DryRun = true
	}

	if len(args) > 0 {
		input := args[0]
		// Detect ticket ID pattern vs freeform
		if looksLikeTicketID(input) {
			req.TicketID = input
			if req.TicketSource == "" {
				req.TicketSource = guessSource(input)
			}
		} else {
			req.Text = input
		}
	}

	// JSON mode
	jsonMode := viper.GetBool("json_output")

	// Create investigation
	resp, err := client.CreateInvestigation(req)
	if err != nil {
		return fmt.Errorf("create investigation: %w", err)
	}

	if req.DryRun {
		if jsonMode {
			b, _ := json.MarshalIndent(resp, "", "  ")
			fmt.Println(string(b))
		} else {
			fmt.Printf("Dry run — would investigate:\n")
			fmt.Printf("  Ticket:  %s\n", req.TicketID)
			fmt.Printf("  Service: %s\n", req.ServiceName)
			fmt.Printf("  Window:  %dm\n", req.WindowMinutes)
		}
		return nil
	}

	if jsonMode {
		b, _ := json.MarshalIndent(resp, "", "  ")
		fmt.Println(string(b))
		return nil
	}

	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	yellow := color.New(color.FgYellow)

	bold.Printf("🔍 Investigation started: %s\n", resp.InvestigationID)
	fmt.Printf("   Estimated time: ~%ds\n\n", resp.EstimatedSeconds)

	// Poll for completion
	watchEnabled, _ := cmd.Flags().GetBool("watch")
	_ = watchEnabled // always watch in interactive mode

	pollInterval := 2 * time.Second
	maxWait := 10 * time.Minute
	deadline := time.Now().Add(maxWait)

	lastStep := ""
	for time.Now().Before(deadline) {
		status, err := client.GetInvestigationStatus(resp.InvestigationID)
		if err != nil {
			yellow.Printf("  Status check failed: %v\n", err)
			time.Sleep(pollInterval)
			continue
		}

		// Print new steps
		for _, step := range status.Progress {
			key := step.Step + step.Status
			if key != lastStep && step.Status != "" {
				icon := "⏳"
				if step.Status == "done" {
					icon = "✓"
				}
				dur := ""
				if step.DurationMs != nil {
					dur = fmt.Sprintf(" (%dms)", *step.DurationMs)
				}
				fmt.Printf("  %s %-25s%s\n", icon, stepLabel(step.Step), dur)
				lastStep = key
			}
		}

		if status.Status == "completed" || status.Status == "failed" {
			break
		}

		time.Sleep(pollInterval)
	}

	// Fetch and display result
	inv, err := client.GetInvestigation(resp.InvestigationID)
	if err != nil {
		return fmt.Errorf("fetch result: %w", err)
	}

	fmt.Println()
	if inv.Status == "failed" {
		color.Red("❌ Investigation failed: %s\n", inv.ErrorMessage)
		return nil
	}

	green.Printf("✅ Investigation complete (%dms)\n\n", inv.DurationMS)
	printInvestigationResult(inv)
	return nil
}

func printInvestigationResult(inv *api.Investigation) {
	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	dim := color.New(color.Faint)

	if len(inv.Hypotheses) == 0 {
		color.Yellow("No hypotheses generated — insufficient signal.")
		return
	}

	top := inv.Hypotheses[0]

	bold.Println("┌─ Root Cause Analysis ─────────────────────────────────────────┐")
	fmt.Println()

	// Confidence bar
	conf := top.Confidence
	bar := strings.Repeat("█", int(conf*20)) + strings.Repeat("░", 20-int(conf*20))
	green.Printf("  Confidence: [%s] %.0f%%\n", bar, conf*100)
	fmt.Println()

	bold.Printf("  PR #%v: %s\n", top.PRID, top.PRTitle)
	if top.PRURL != "" {
		dim.Printf("  %s\n", top.PRURL)
	}
	fmt.Printf("  Author:  %s\n", top.PRAuthor)
	fmt.Printf("  Merged:  %s\n", top.PRMergedAt)
	if top.FilePath != "" {
		fmt.Printf("  File:    %s", top.FilePath)
		if top.LineNumber != nil {
			fmt.Printf(":%d", *top.LineNumber)
		}
		fmt.Println()
	}
	fmt.Printf("  Change:  %s\n", top.DiffType)

	if top.Narrative != "" {
		fmt.Println()
		bold.Println("  Analysis:")
		fmt.Printf("  %s\n", wrapText(top.Narrative, 68, "  "))
	}

	if len(inv.Hypotheses) > 1 {
		fmt.Println()
		dim.Printf("  Other hypotheses: %d (run 'bugpilot history %s' for details)\n",
			len(inv.Hypotheses)-1, inv.InvestigationID)
	}

	if inv.BlastRadius != nil && inv.BlastRadius.Count > 0 {
		fmt.Println()
		bold.Printf("  Blast radius: %d affected records", inv.BlastRadius.Count)
		if inv.BlastRadius.ValueUSD > 0 {
			bold.Printf(" (~$%.0f at risk)", inv.BlastRadius.ValueUSD)
		}
		fmt.Println()
	}

	fmt.Println()
	bold.Println("└───────────────────────────────────────────────────────────────┘")
	fmt.Println()

	// Interactive feedback prompt
	if !isTerminal() {
		return
	}
	fmt.Print("  Is this correct? [y]es / [n]o / [s]kip: ")
	var ans string
	_, _ = fmt.Scanln(&ans)
	ans = strings.ToLower(strings.TrimSpace(ans))
	if ans == "y" || ans == "yes" {
		fmt.Println("  Feedback recorded: confirmed")
		// Submit feedback
		apiKey, _ := config.LoadAPIKey()
		cfg, _ := config.Load()
		client := api.New(cfg.BaseURL, apiKey)
		_ = client.SubmitFeedback(inv.InvestigationID, api.FeedbackRequest{
			Feedback:    "confirmed",
			HypothesisRank: 1,
		})
	} else if ans == "n" || ans == "no" {
		fmt.Print("  What was the actual cause? (optional): ")
		var cause string
		_, _ = fmt.Scanln(&cause)
		apiKey, _ := config.LoadAPIKey()
		cfg, _ := config.Load()
		client := api.New(cfg.BaseURL, apiKey)
		_ = client.SubmitFeedback(inv.InvestigationID, api.FeedbackRequest{
			Feedback:    "refuted",
			HypothesisRank: 1,
			Cause:       cause,
		})
		fmt.Println("  Feedback recorded: refuted")
	}
}

func looksLikeTicketID(s string) bool {
	if len(s) > 50 {
		return false
	}
	// PROJ-123 pattern
	for i, c := range s {
		if c == '-' && i > 0 {
			return true
		}
	}
	// #123 pattern
	if strings.HasPrefix(s, "#") {
		return true
	}
	return false
}

func guessSource(ticketID string) string {
	upper := strings.ToUpper(ticketID)
	if strings.HasPrefix(upper, "PROJ-") || strings.Contains(upper, "-") {
		return "jira"
	}
	return "cli"
}

func stepLabel(step string) string {
	labels := map[string]string{
		"resolve_window":      "Resolving time window",
		"load_connectors":     "Loading connectors",
		"fetch_events":        "Fetching events",
		"build_graph":         "Building code graph",
		"rank_hypotheses":     "Ranking hypotheses",
		"generate_narrative":  "Generating analysis",
		"persist_results":     "Saving results",
	}
	if l, ok := labels[step]; ok {
		return l
	}
	return step
}

func wrapText(text string, width int, indent string) string {
	words := strings.Fields(text)
	var lines []string
	var line strings.Builder
	for _, word := range words {
		if line.Len()+len(word)+1 > width && line.Len() > 0 {
			lines = append(lines, line.String())
			line.Reset()
			line.WriteString(indent)
		}
		if line.Len() > len(indent) {
			line.WriteString(" ")
		}
		line.WriteString(word)
	}
	if line.Len() > 0 {
		lines = append(lines, line.String())
	}
	return strings.Join(lines, "\n")
}

func isTerminal() bool {
	fi, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return (fi.Mode() & os.ModeCharDevice) != 0
}
