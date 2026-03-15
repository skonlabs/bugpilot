package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	cfgFile string

	rootCmd = &cobra.Command{
		Use:   "bugpilot",
		Short: "BugPilot — trace bugs to the exact PR that introduced them",
		Long: `BugPilot is a CLI tool that investigates customer-reported functional bugs
and traces them to the specific GitHub PR, file, and line that introduced them.

Get started:
  bugpilot init                     # Set up API key and connect sources
  bugpilot investigate TICKET-123   # Run an investigation
  bugpilot history                  # View past investigations`,
	}
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)

	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "",
		"config file (default: $HOME/.bugpilot/config.yaml)")
	rootCmd.PersistentFlags().String("api-key", "",
		"API key (overrides config file)")
	rootCmd.PersistentFlags().String("base-url", "",
		"API base URL (overrides config file)")
	rootCmd.PersistentFlags().Bool("json", false,
		"Output as JSON")

	_ = viper.BindPFlag("api_key", rootCmd.PersistentFlags().Lookup("api-key"))
	_ = viper.BindPFlag("base_url", rootCmd.PersistentFlags().Lookup("base-url"))
	_ = viper.BindPFlag("json_output", rootCmd.PersistentFlags().Lookup("json"))
}

func initConfig() {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			fmt.Fprintln(os.Stderr, "Could not determine home directory:", err)
			os.Exit(1)
		}
		viper.AddConfigPath(home + "/.bugpilot")
		viper.SetConfigType("yaml")
		viper.SetConfigName("config")
	}

	viper.SetEnvPrefix("BUGPILOT")
	viper.AutomaticEnv()

	// Ignore if config file not found — user may not have run `init` yet
	_ = viper.ReadInConfig()
}
