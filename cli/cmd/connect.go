package cmd

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"github.com/skonlabs/bugpilot/internal/api"
	"github.com/skonlabs/bugpilot/internal/config"
)

var connectCmd = &cobra.Command{
	Use:   "connect [connector-type]",
	Short: "Connect data sources (GitHub, Sentry, Jira, etc.)",
	Long: `Connect BugPilot to your data sources.

Available connectors:
  github      — GitHub repositories (required for PR analysis)
  sentry      — Sentry error tracking
  jira        — Jira tickets
  freshdesk   — Freshdesk support tickets
  email       — Email/IMAP support inbox
  database    — Customer database (blast radius)
  log-files   — Local log files

Examples:
  bugpilot connect github
  bugpilot connect sentry
  bugpilot connect list
  bugpilot connect github --name secondary-org`,
}

var connectListCmd = &cobra.Command{
	Use:   "list",
	Short: "List connected sources",
	RunE:  runConnectList,
}

func init() {
	rootCmd.AddCommand(connectCmd)
	rootCmd.AddCommand(doctorCmd)
	connectCmd.AddCommand(connectListCmd)

	for _, ct := range []string{"github", "sentry", "jira", "freshdesk", "email", "database", "log-files"} {
		ct := ct // capture
		subCmd := &cobra.Command{
			Use:   ct,
			Short: fmt.Sprintf("Connect %s", ct),
			RunE: func(cmd *cobra.Command, args []string) error {
				return runConnect(cmd, ct, args)
			},
		}
		subCmd.Flags().String("name", "default", "Connector instance name")
		subCmd.Flags().String("service", "", "Scope to service name")
		connectCmd.AddCommand(subCmd)
	}
}

func runConnectList(cmd *cobra.Command, args []string) error {
	apiKey, err := config.LoadAPIKey()
	if err != nil || apiKey == "" {
		return fmt.Errorf("not configured: run 'bugpilot init' first")
	}
	cfg, _ := config.Load()
	client := newClient(cfg, apiKey)

	connectors, err := client.ListConnectors()
	if err != nil {
		return fmt.Errorf("list connectors: %w", err)
	}

	if len(connectors) == 0 {
		fmt.Println("No connectors configured.")
		fmt.Println("Run 'bugpilot connect github' to get started.")
		return nil
	}

	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	red := color.New(color.FgRed)
	yellow := color.New(color.FgYellow)

	bold.Printf("%-12s  %-12s  %-15s  %s\n", "TYPE", "NAME", "STATUS", "LAST CHECK")
	fmt.Println(strings.Repeat("─", 60))

	for _, c := range connectors {
		statusColor := yellow
		if c.Status == "active" {
			statusColor = green
		} else if strings.Contains(c.Status, "error") {
			statusColor = red
		}
		fmt.Printf("%-12s  %-12s  ", c.Type, c.Name)
		statusColor.Printf("%-15s", c.Status)
		fmt.Printf("  %s\n", c.LastHealthCheck)
	}
	return nil
}

func runConnect(cmd *cobra.Command, connectorType string, args []string) error {
	apiKey, err := config.LoadAPIKey()
	if err != nil || apiKey == "" {
		return fmt.Errorf("not configured: run 'bugpilot init' first")
	}

	cfg, _ := config.Load()
	client := newClient(cfg, apiKey)

	name, _ := cmd.Flags().GetString("name")
	service, _ := cmd.Flags().GetString("service")

	// Normalize type
	apiType := strings.ReplaceAll(connectorType, "-", "_")
	if apiType == "email" {
		apiType = "email_imap"
	}

	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	yellow := color.New(color.FgYellow)
	red := color.New(color.FgRed)

	bold.Printf("🔌 Connecting %s (instance: %s)\n\n", connectorType, name)

	connConfig, err := promptConnectorConfig(apiType)
	if err != nil {
		return err
	}

	serviceMap := map[string]interface{}{}
	if service != "" {
		serviceMap[service] = true
	}

	yellow.Print("Saving connector... ")
	resp, err := client.AddConnector(apiType, api.AddConnectorRequest{
		Name:       name,
		Config:     connConfig,
		ServiceMap: serviceMap,
	})
	if err != nil {
		red.Println("✗")
		return fmt.Errorf("add connector: %w", err)
	}
	green.Printf("✓ (id: %s)\n", resp.ConnectorID)

	// Health check
	yellow.Print("Running health check... ")
	health, err := client.ConnectorHealth(apiType, name)
	if err != nil {
		red.Printf("✗ (%v)\n", err)
	} else {
		status, _ := health["status"].(string)
		message, _ := health["message"].(string)
		if status == "ok" {
			green.Printf("✓ %s\n", message)
		} else {
			red.Printf("✗ %s\n", message)
		}
	}

	return nil
}

func promptConnectorConfig(connectorType string) (map[string]interface{}, error) {
	reader := bufio.NewReader(os.Stdin)
	cfg := map[string]interface{}{}

	prompt := func(label, envHint string) string {
		if envHint != "" {
			fmt.Printf("  %s (or set %s): ", label, envHint)
		} else {
			fmt.Printf("  %s: ", label)
		}
		line, _ := reader.ReadString('\n')
		return strings.TrimSpace(line)
	}

	switch connectorType {
	case "github":
		fmt.Println("GitHub connector — choose auth method:")
		fmt.Println("  1) Personal Access Token (simpler)")
		fmt.Println("  2) GitHub App (recommended for production)")
		fmt.Print("  Choice [1]: ")
		choice, _ := reader.ReadString('\n')
		choice = strings.TrimSpace(choice)

		cfg["org"] = prompt("GitHub org or user", "")
		if choice == "2" {
			cfg["app_id"] = prompt("GitHub App ID", "GITHUB_APP_ID")
			fmt.Println("  Paste GitHub App private key (PEM), end with '---END---':")
			var keyLines []string
			for {
				line, _ := reader.ReadString('\n')
				line = strings.TrimRight(line, "\n")
				if line == "---END---" {
					break
				}
				keyLines = append(keyLines, line)
			}
			cfg["private_key"] = strings.Join(keyLines, "\n")
		} else {
			cfg["token"] = prompt("Personal Access Token (ghp_...)", "GITHUB_TOKEN")
		}
		repos := prompt("Repos to index (comma-separated, or leave blank for all)", "")
		if repos != "" {
			repoList := strings.Split(repos, ",")
			trimmed := make([]string, len(repoList))
			for i, r := range repoList {
				trimmed[i] = strings.TrimSpace(r)
			}
			cfg["repos"] = trimmed
		}

	case "sentry":
		cfg["auth_token"] = prompt("Sentry Auth Token", "SENTRY_AUTH_TOKEN")
		cfg["org_slug"] = prompt("Sentry org slug", "")
		projects := prompt("Project slugs (comma-separated, or blank for all)", "")
		if projects != "" {
			slugs := strings.Split(projects, ",")
			for i, s := range slugs {
				slugs[i] = strings.TrimSpace(s)
			}
			cfg["project_slugs"] = slugs
		}

	case "jira":
		cfg["base_url"] = prompt("Jira base URL (e.g. https://company.atlassian.net)", "")
		cfg["email"] = prompt("Jira account email", "JIRA_EMAIL")
		cfg["api_token"] = prompt("Jira API token", "JIRA_API_TOKEN")
		projects := prompt("Project keys (comma-separated, e.g. ENG,BUG)", "")
		if projects != "" {
			keys := strings.Split(projects, ",")
			for i, k := range keys {
				keys[i] = strings.TrimSpace(k)
			}
			cfg["project_keys"] = keys
		}

	case "freshdesk":
		cfg["domain"] = prompt("Freshdesk domain (e.g. company.freshdesk.com)", "")
		cfg["api_key"] = prompt("Freshdesk API key", "FRESHDESK_API_KEY")

	case "email_imap":
		cfg["host"] = prompt("IMAP host (e.g. imap.gmail.com)", "")
		cfg["username"] = prompt("Email address", "")
		cfg["password"] = prompt("App password", "EMAIL_APP_PASSWORD")
		folder := prompt("Folder [INBOX]", "")
		if folder != "" {
			cfg["folder"] = folder
		}

	case "database":
		cfg["dsn"] = prompt("Database DSN (postgresql://user:pass@host/db)", "DATABASE_URL")
		fmt.Println("  Role:")
		fmt.Println("    1) blast_radius — count affected records")
		fmt.Println("    2) error_log_table — read error log table")
		fmt.Println("    3) both")
		fmt.Print("  Choice [2]: ")
		roleLine, _ := reader.ReadString('\n')
		roles := map[string]string{"1": "blast_radius", "2": "error_log_table", "3": "both"}
		role := roles[strings.TrimSpace(roleLine)]
		if role == "" {
			role = "error_log_table"
		}
		cfg["role"] = role

	case "log_files":
		fmt.Println("  Enter log file paths or glob patterns (one per line, empty to finish):")
		var paths []string
		for {
			fmt.Print("  Path: ")
			line, _ := reader.ReadString('\n')
			line = strings.TrimSpace(line)
			if line == "" {
				break
			}
			paths = append(paths, line)
		}
		cfg["paths"] = paths
		fmt.Print("  Format (json/text) [json]: ")
		fmtLine, _ := reader.ReadString('\n')
		fmtLine = strings.TrimSpace(fmtLine)
		if fmtLine == "" {
			fmtLine = "json"
		}
		cfg["format"] = fmtLine

	default:
		return nil, fmt.Errorf("unknown connector type: %s", connectorType)
	}

	return cfg, nil
}

// doctor checks all connectors
var doctorCmd = &cobra.Command{
	Use:   "doctor",
	Short: "Check all connector health",
	RunE:  runDoctor,
}

func runDoctor(cmd *cobra.Command, args []string) error {
	apiKey, err := config.LoadAPIKey()
	if err != nil || apiKey == "" {
		return fmt.Errorf("not configured: run 'bugpilot init' first")
	}
	cfg, _ := config.Load()
	client := newClient(cfg, apiKey)

	bold := color.New(color.Bold)
	green := color.New(color.FgGreen)
	red := color.New(color.FgRed)
	yellow := color.New(color.FgYellow)

	bold.Println("🔧 BugPilot Doctor")

	// Check API connection
	yellow.Print("  API connection... ")
	_, err = client.ValidateKey(api.ValidateKeyRequest{})
	if err != nil {
		red.Printf("✗ %v\n", err)
	} else {
		green.Println("✓")
	}

	// Check connectors
	connectors, err := client.ListConnectors()
	if err != nil {
		red.Printf("  Failed to list connectors: %v\n", err)
		return nil
	}

	if len(connectors) == 0 {
		yellow.Println("  No connectors configured.")
		fmt.Println("  Run 'bugpilot connect github' to get started.")
		return nil
	}

	fmt.Println()
	bold.Println("  Connectors:")

	hasGitHub := false
	for _, c := range connectors {
		if c.Type == "github" {
			hasGitHub = true
		}
		health, err := client.ConnectorHealth(c.Type, c.Name)
		if err != nil {
			fmt.Printf("  %-12s %-10s  ", c.Type, c.Name)
			red.Printf("✗ %v\n", err)
			continue
		}
		status, _ := health["status"].(string)
		message, _ := health["message"].(string)
		fmt.Printf("  %-12s %-10s  ", c.Type, c.Name)
		if status == "ok" {
			green.Printf("✓ %s\n", message)
		} else {
			red.Printf("✗ %s\n", message)
		}
	}

	fmt.Println()
	if !hasGitHub {
		yellow.Println("  ⚠ No GitHub connector — PR analysis will not work.")
		fmt.Println("    Run: bugpilot connect github")
	}

	// Serialize result for JSON mode
	if viper.GetBool("json_output") {
		b, _ := json.MarshalIndent(connectors, "", "  ")
		fmt.Println(string(b))
	}

	return nil
}
