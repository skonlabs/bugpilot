// Package update handles atomic binary self-update.
package update

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

const releaseAPIURL = "https://api.github.com/repos/skonlabs/bugpilot/releases/latest"

type Release struct {
	TagName string  `json:"tag_name"`
	Assets  []Asset `json:"assets"`
}

type Asset struct {
	Name               string `json:"name"`
	BrowserDownloadURL string `json:"browser_download_url"`
}

// Download downloads the latest release binary and replaces the current executable atomically.
// Steps:
//  1. Download to a random temp file in the same directory as the binary
//  2. Set executable permissions
//  3. os.Rename to current executable path (atomic on same filesystem)
func Download(latestURL string) error {
	// Find current executable
	exe, err := os.Executable()
	if err != nil {
		return fmt.Errorf("find executable: %w", err)
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		return fmt.Errorf("resolve symlinks: %w", err)
	}

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Get(latestURL)
	if err != nil {
		return fmt.Errorf("download: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("download status %d", resp.StatusCode)
	}

	// Write to a randomly-named temp file in the same directory to allow atomic rename
	tmpF, err := os.CreateTemp(filepath.Dir(exe), "bugpilot-*.tmp")
	if err != nil {
		return fmt.Errorf("create temp file: %w", err)
	}
	tmpFile := tmpF.Name()

	if _, err := io.Copy(tmpF, resp.Body); err != nil {
		tmpF.Close()
		os.Remove(tmpFile)
		return fmt.Errorf("write temp file: %w", err)
	}
	tmpF.Close()

	// Set executable permissions before the rename so the binary is ready on swap
	if err := os.Chmod(tmpFile, 0755); err != nil {
		os.Remove(tmpFile)
		return fmt.Errorf("set permissions: %w", err)
	}

	// Atomic replace
	if err := os.Rename(tmpFile, exe); err != nil {
		os.Remove(tmpFile)
		return fmt.Errorf("replace binary: %w", err)
	}

	return nil
}

// AssetURLForPlatform returns the download URL for the current platform.
func AssetURLForPlatform(assets []Asset) (string, error) {
	goos := runtime.GOOS
	goarch := runtime.GOARCH

	// OS names as used in release asset filenames
	osMap := map[string]string{
		"linux":   "linux",
		"darwin":  "macos", // release assets are named "macos", not "darwin"
		"windows": "windows",
	}
	osName, ok := osMap[goos]
	if !ok {
		return "", fmt.Errorf("unsupported OS: %s", goos)
	}

	// Arch names match Go's GOARCH values in release asset filenames (amd64, arm64)
	archName := goarch

	for _, asset := range assets {
		name := strings.ToLower(asset.Name)
		if strings.Contains(name, osName) && strings.Contains(name, archName) {
			if goos == "windows" && !strings.HasSuffix(name, ".exe") {
				continue
			}
			return asset.BrowserDownloadURL, nil
		}
	}
	return "", fmt.Errorf("no asset found for %s/%s", goos, goarch)
}
