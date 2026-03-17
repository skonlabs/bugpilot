package cmd

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"github.com/skonlabs/bugpilot/internal/update"
)

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update bugpilot to the latest version",
	RunE:  runUpdate,
}

func init() {
	rootCmd.AddCommand(updateCmd)
	updateCmd.Flags().Bool("check-only", false, "Check for updates without installing")
}

func runUpdate(cmd *cobra.Command, args []string) error {
	yellow := color.New(color.FgYellow)
	green := color.New(color.FgGreen)
	red := color.New(color.FgRed)
	bold := color.New(color.Bold)

	yellow.Print("Checking for updates... ")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get("https://api.github.com/repos/skonlabs/bugpilot/releases/latest")
	if err != nil {
		red.Printf("✗ (%v)\n", err)
		return fmt.Errorf("check update: %w", err)
	}
	defer resp.Body.Close()

	var release update.Release
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		red.Println("✗ (invalid response)")
		return fmt.Errorf("parse release: %w", err)
	}

	latest := release.TagName
	if latest == "" {
		red.Println("✗ (no releases found)")
		return fmt.Errorf("no releases found")
	}

	if latest == Version {
		green.Printf("✓ Already up to date (%s)\n", Version)
		return nil
	}

	fmt.Printf("Current: %s  →  Latest: %s\n", Version, bold.Sprint(latest))

	checkOnly, _ := cmd.Flags().GetBool("check-only")
	if checkOnly {
		yellow.Printf("⚡ Run 'bugpilot update' to install %s\n", latest)
		return nil
	}

	assetURL, err := update.AssetURLForPlatform(release.Assets)
	if err != nil {
		return fmt.Errorf("find asset: %w", err)
	}

	yellow.Printf("Downloading %s...\n", latest)

	var lastPct int
	progress := func(downloaded, total int64) {
		if total <= 0 {
			return
		}
		pct := int(downloaded * 100 / total)
		if pct != lastPct && pct%10 == 0 {
			fmt.Printf("  %d%%\n", pct)
			lastPct = pct
		}
	}

	if err := update.Download(assetURL, progress); err != nil {
		red.Printf("✗ Update failed: %v\n", err)
		return err
	}

	green.Printf("✓ Updated to %s — restart any open terminals to use the new version.\n", latest)
	return nil
}
