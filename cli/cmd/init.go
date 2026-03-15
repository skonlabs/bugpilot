package cmd

import (
	"bufio"
	"fmt"
	"os"
	"runtime"
	"strings"
	"time"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"github.com/skonlabs/bugpilot/internal/api"
	"github.com/skonlabs/bugpilot/internal/config"
)

const (
	termsVersion = "1.0"
	termsURL     = "https://ekonomical.com/terms"
	cliVersion   = "v1.0.0"
)

var initCmd = &cobra.Command{
	Use:   "init",
	Short: "Set up BugPilot with your API key and accept the Terms of Service",
	Long: `Initialize BugPilot (5 steps):

  Step 1/5 — API key validation
  Step 2/5 — Terms of Service acceptance
  Step 3/5 — Default service name (optional)
  Step 4/5 — Write configuration
  Step 5/5 — Verify connection`,
	RunE: runInit,
}

func init() {
	rootCmd.AddCommand(initCmd)
	initCmd.Flags().Bool("non-interactive", false, "Non-interactive mode (requires --api-key flag)")
}

func runInit(cmd *cobra.Command, args []string) error {
	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	yellow := color.New(color.FgYellow)
	red := color.New(color.FgRed)

	bold.Println("🔧 BugPilot Setup")
	fmt.Println()

	reader := bufio.NewReader(os.Stdin)

	// ── Step 1: API Key ────────────────────────────────────────────────────────
	bold.Println("Step 1/5 — API Key Validation")
	fmt.Println("  Get your API key at: https://app.ekonomical.com/settings/api-keys")
	fmt.Print("  Enter your API key (bp_live_... or bp_test_...): ")

	var apiKey string
	apiKeyFlag, _ := cmd.Root().PersistentFlags().GetString("api-key")
	if apiKeyFlag != "" {
		apiKey = apiKeyFlag
		fmt.Println("  Using --api-key flag")
	} else {
		line, err := reader.ReadString('\n')
		if err != nil {
			return fmt.Errorf("read api key: %w", err)
		}
		apiKey = strings.TrimSpace(line)
	}

	if !strings.HasPrefix(apiKey, "bp_live_") && !strings.HasPrefix(apiKey, "bp_test_") {
		red.Println("  ✗ API key must start with bp_live_ or bp_test_")
		return fmt.Errorf("invalid API key format")
	}

	// Load base URL
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}
	baseURL := cfg.BaseURL
	baseURLFlag, _ := cmd.Root().PersistentFlags().GetString("base-url")
	if baseURLFlag != "" {
		baseURL = baseURLFlag
	}

	client := api.New(baseURL, apiKey)

	// ── Step 2: Terms of Service ───────────────────────────────────────────────
	fmt.Println()
	bold.Println("Step 2/5 — Terms of Service")
	fmt.Printf("  Please read the Terms of Service at: %s\n", termsURL)
	fmt.Print("  Do you accept the Terms of Service? [y/N]: ")

	termsLine, err := reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("read terms: %w", err)
	}
	termsLine = strings.ToLower(strings.TrimSpace(termsLine))
	if termsLine != "y" && termsLine != "yes" {
		yellow.Println("  Terms not accepted. Setup cancelled.")
		return fmt.Errorf("terms not accepted")
	}

	termsAcceptedAt := time.Now().UTC().Format(time.RFC3339)

	// Validate key with T&C
	yellow.Print("  Validating API key... ")
	validateResp, err := client.ValidateKey(api.ValidateKeyRequest{
		TermsAccepted:   true,
		TermsVersion:    termsVersion,
		TermsAcceptedAt: termsAcceptedAt,
		CLIVersion:      cliVersion,
		Platform:        runtime.GOOS + "/" + runtime.GOARCH,
	})
	if err != nil {
		red.Println("✗")
		return fmt.Errorf("key validation failed: %w", err)
	}
	green.Printf("✓ Connected as %s (%s plan)\n", validateResp.OrgName, validateResp.Plan)

	// ── Step 3: Service name ───────────────────────────────────────────────────
	fmt.Println()
	bold.Println("Step 3/5 — Default Service (optional)")
	fmt.Print("  Default service name to investigate (e.g. 'payments', press Enter to skip): ")

	serviceLine, err := reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("read service: %w", err)
	}
	_ = strings.TrimSpace(serviceLine) // stored in future connector config

	// ── Step 4: Write configuration ────────────────────────────────────────────
	fmt.Println()
	bold.Println("Step 4/5 — Writing Configuration")
	yellow.Print("  Saving ~/.bugpilot/config.yaml... ")

	newCfg := &config.Config{
		APIKey:  apiKey,
		BaseURL: baseURL,
		OrgID:   validateResp.OrgID,
		OrgName: validateResp.OrgName,
		Plan:    validateResp.Plan,
	}

	if err := config.Save(newCfg); err != nil {
		red.Println("✗")
		return fmt.Errorf("save config: %w", err)
	}
	green.Println("✓")

	// ── Step 5: Verify connection ──────────────────────────────────────────────
	fmt.Println()
	bold.Println("Step 5/5 — Verify Connection")
	yellow.Print("  Testing API connection... ")
	_, err = client.ValidateKey(api.ValidateKeyRequest{})
	if err != nil {
		red.Println("✗")
		return fmt.Errorf("connection test failed: %w", err)
	}
	green.Println("✓")

	fmt.Println()
	bold.Println("✅ BugPilot is ready!")
	fmt.Println()
	fmt.Println("  Next steps:")
	fmt.Println("    bugpilot connect github    # Connect your GitHub repositories")
	fmt.Println("    bugpilot connect sentry    # Connect Sentry for error signals")
	fmt.Println("    bugpilot investigate TICKET-123  # Run your first investigation")
	fmt.Println("    bugpilot doctor            # Verify all connectors are healthy")

	return nil
}
