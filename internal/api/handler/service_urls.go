package handler

import (
	"dev_metric/config"
	"fmt"
)

func ensureServiceConfigLoaded() *config.Config {
	if cfg := config.Get(); cfg != nil {
		return cfg
	}
	cfg, err := config.Load("config.yaml")
	if err != nil {
		return nil
	}
	return cfg
}

func normalizeLoopbackHost(host string) string {
	if host == "" || host == "0.0.0.0" {
		return "localhost"
	}
	return host
}

func aiBaseURL() string {
	cfg := ensureServiceConfigLoaded()
	if cfg == nil {
		return "http://localhost:18081"
	}
	return fmt.Sprintf("http://%s:%d", normalizeLoopbackHost(cfg.AI.Host), cfg.AI.Port)
}
