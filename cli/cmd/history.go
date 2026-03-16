package cmd

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"github.com/skonlabs/bugpilot/internal/config"
)

var historyCmd = &cobra.Command{
	Use:   "history [investigation-id]",
	Short: "View past investigations",
	Long: `List past investigations or view a specific investigation's full details.

Examples:
  bugpilot history                # List recent investigations
  bugpilot history INV-042        # View investigation details
  bugpilot history --limit 50     # Show more results`,
	Args: cobra.MaximumNArgs(1),
	RunE: runHistory,
}

func init() {
	rootCmd.AddCommand(historyCmd)
	historyCmd.Flags().Int("limit", 20, "Number of investigations to show")
	historyCmd.Flags().Int("offset", 0, "Offset for pagination")
}

func runHistory(cmd *cobra.Command, args []string) error {
	apiKey, err := config.LoadAPIKey()
	if err != nil || apiKey == "" {
		return fmt.Errorf("not configured: run 'bugpilot init' first")
	}

	cfg, _ := config.Load()
	client := newClient(cfg, apiKey)
	jsonMode := viper.GetBool("json_output")

	// Show specific investigation
	if len(args) == 1 {
		inv, err := client.GetInvestigation(args[0])
		if err != nil {
			return fmt.Errorf("fetch investigation: %w", err)
		}
		if jsonMode {
			b, _ := json.MarshalIndent(inv, "", "  ")
			fmt.Println(string(b))
			return nil
		}
		printInvestigationResult(inv)
		return nil
	}

	// List investigations
	limit, _ := cmd.Flags().GetInt("limit")
	offset, _ := cmd.Flags().GetInt("offset")
	history, err := client.GetHistory(limit, offset)
	if err != nil {
		return fmt.Errorf("fetch history: %w", err)
	}

	if jsonMode {
		b, _ := json.MarshalIndent(history, "", "  ")
		fmt.Println(string(b))
		return nil
	}

	if len(history.Items) == 0 {
		fmt.Println("No investigations found.")
		return nil
	}

	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	red := color.New(color.FgRed)
	yellow := color.New(color.FgYellow)
	dim := color.New(color.Faint)

	bold.Printf("Investigations (%d total)\n\n", history.Total)
	bold.Printf("%-12s  %-10s  %-15s  %-10s  %-6s  %s\n",
		"ID", "STATUS", "SERVICE", "SOURCE", "CONF%", "TRIGGER")
	fmt.Println(strings.Repeat("─", 80))

	for _, item := range history.Items {
		statusColor := dim
		switch item.Status {
		case "completed":
			statusColor = green
		case "failed":
			statusColor = red
		case "running", "queued":
			statusColor = yellow
		}

		conf := ""
		if item.TopConfidence > 0 {
			conf = fmt.Sprintf("%.0f%%", item.TopConfidence*100)
		}

		service := item.ServiceName
		if service == "" {
			service = "-"
		}
		if len(service) > 12 {
			service = service[:12]
		}

		trigger := item.TriggerRef
		if len(trigger) > 20 {
			trigger = trigger[:20]
		}

		// Parse queued_at
		queuedAt := ""
		if item.QueuedAt != "" {
			t, err := time.Parse(time.RFC3339, item.QueuedAt)
			if err == nil {
				queuedAt = t.Format("01-02 15:04")
			}
		}

		feedback := ""
		if item.Feedback == "confirmed" {
			feedback = " ✓"
		} else if item.Feedback == "refuted" {
			feedback = " ✗"
		}

		fmt.Printf("%-12s  ", item.InvestigationID)
		statusColor.Printf("%-10s", item.Status)
		fmt.Printf("  %-15s  %-10s  %-6s  %s  %s%s\n",
			service, item.TriggerSource, conf, trigger, queuedAt, feedback)
	}

	fmt.Println()
	if history.Total > offset+limit {
		dim.Printf("Showing %d-%d of %d. Use --offset %d to see more.\n",
			offset+1, offset+len(history.Items), history.Total, offset+limit)
	}

	return nil
}
