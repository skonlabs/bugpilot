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
	fmt.Printf("Latest: %s, Current: %s\n", latest, Version)

	if latest == Version {
		green.Println("✓ You are already up to date.")
		return nil
	}

	checkOnly, _ := cmd.Flags().GetBool("check-only")
	if checkOnly {
		yellow.Printf("⚡ Update available: %s\n", latest)
		return nil
	}

	assetURL, err := update.AssetURLForPlatform(release.Assets)
	if err != nil {
		return fmt.Errorf("find asset: %w", err)
	}

	yellow.Printf("Downloading %s from %s\n", latest, assetURL)
	if err := update.Download(assetURL); err != nil {
		red.Printf("✗ Update failed: %v\n", err)
		return err
	}

	green.Printf("✓ Updated to %s\n", latest)
	return nil
}
