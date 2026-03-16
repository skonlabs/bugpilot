package cmd

import (
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"github.com/skonlabs/bugpilot/internal/config"
)

var reportCmd = &cobra.Command{
	Use:   "report <investigation-id>",
	Short: "Generate or download an investigation report",
	Long: `Generate a markdown report for an investigation.

Examples:
  bugpilot report INV-042
  bugpilot report INV-042 --output report.md
  bugpilot report INV-042 --confluence --space ENG`,
	Args: cobra.ExactArgs(1),
	RunE: runReport,
}

func init() {
	rootCmd.AddCommand(reportCmd)
	reportCmd.Flags().StringP("output", "o", "", "Save report to file")
	reportCmd.Flags().Bool("confluence", false, "Push to Confluence")
	reportCmd.Flags().String("space", "", "Confluence space key")
	reportCmd.Flags().String("parent", "", "Confluence parent page ID")
}

func runReport(cmd *cobra.Command, args []string) error {
	invID := args[0]
	apiKey, err := config.LoadAPIKey()
	if err != nil || apiKey == "" {
		return fmt.Errorf("not configured: run 'bugpilot init' first")
	}
	cfg, _ := config.Load()
	client := newClient(cfg, apiKey)

	outputFile, _ := cmd.Flags().GetString("output")
	pushConfluence, _ := cmd.Flags().GetBool("confluence")
	spaceKey, _ := cmd.Flags().GetString("space")
	parentID, _ := cmd.Flags().GetString("parent")

	green := color.New(color.FgGreen)
	yellow := color.New(color.FgYellow)
	red := color.New(color.FgRed)

	if pushConfluence {
		if spaceKey == "" {
			return fmt.Errorf("--space is required for Confluence push")
		}
		yellow.Print("Pushing to Confluence... ")

		var result map[string]interface{}
		err = client.Do("POST", "/v1/reports/"+invID+"/confluence",
			map[string]interface{}{
				"space_key":      spaceKey,
				"parent_page_id": parentID,
			}, &result)
		if err != nil {
			red.Printf("✗ %v\n", err)
			return err
		}
		green.Println("✓")
		if url, ok := result["confluence_url"].(string); ok {
			fmt.Printf("  %s\n", url)
		}
		return nil
	}

	// Download report
	if outputFile != "" {
		yellow.Printf("Downloading report for %s... ", invID)
		httpClient := &http.Client{}
		req, err := http.NewRequest("GET",
			cfg.BaseURL+"/v1/reports/"+invID+"/download", nil)
		if err != nil {
			return fmt.Errorf("create request: %w", err)
		}
		req.Header.Set("Authorization", "Bearer "+apiKey)
		resp, err := httpClient.Do(req)
		if err != nil {
			red.Printf("✗ %v\n", err)
			return err
		}
		defer resp.Body.Close()

		f, err := os.Create(outputFile)
		if err != nil {
			return fmt.Errorf("create file: %w", err)
		}
		defer f.Close()
		if _, err := io.Copy(f, resp.Body); err != nil {
			return fmt.Errorf("write file: %w", err)
		}
		green.Printf("✓ Saved to %s\n", outputFile)
		return nil
	}

	// Print to stdout
	var result map[string]interface{}
	if err := client.Do("POST", "/v1/reports/"+invID, nil, &result); err != nil {
		return fmt.Errorf("generate report: %w", err)
	}
	if report, ok := result["report"].(string); ok {
		fmt.Println(report)
	}
	return nil
}
