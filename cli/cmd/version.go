package cmd

import (
	"encoding/json"
	"fmt"
	"net/http"
	"runtime"
	"time"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
)

// Version is set at build time via -ldflags.
var Version = "dev"

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print version and check for updates",
	Run:   runVersion,
}

func init() {
	rootCmd.AddCommand(versionCmd)
	versionCmd.Flags().Bool("check", false, "Check for updates only (no output otherwise)")
}

func runVersion(cmd *cobra.Command, args []string) {
	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	yellow := color.New(color.FgYellow)

	bold.Printf("bugpilot %s\n", Version)
	fmt.Printf("  Go:       %s\n", runtime.Version())
	fmt.Printf("  Platform: %s/%s\n", runtime.GOOS, runtime.GOARCH)
	fmt.Println()

	// Check for updates from GitHub releases
	yellow.Print("Checking for updates... ")
	latest, releaseURL, err := fetchLatestVersion()
	if err != nil {
		fmt.Printf("(update check failed: %v)\n", err)
		return
	}

	if latest == Version || latest == "" {
		green.Println("You are up to date.")
	} else {
		yellow.Printf("\n⚡ Update available: %s → %s\n", Version, latest)
		fmt.Printf("   Run: bugpilot update\n")
		fmt.Printf("   Or:  %s\n", releaseURL)
	}
}

type githubRelease struct {
	TagName string `json:"tag_name"`
	HTMLURL string `json:"html_url"`
	Assets  []struct {
		Name               string `json:"name"`
		BrowserDownloadURL string `json:"browser_download_url"`
	} `json:"assets"`
}

func fetchLatestVersion() (string, string, error) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get("https://api.github.com/repos/skonlabs/bugpilot/releases/latest")
	if err != nil {
		return "", "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", "", fmt.Errorf("github api status %d", resp.StatusCode)
	}

	var release githubRelease
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return "", "", err
	}
	return release.TagName, release.HTMLURL, nil
}
