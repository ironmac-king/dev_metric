package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Database  DatabaseConfig  `yaml:"database"`
	StarRocks StarRocksConfig `yaml:"starrocks"`
	DingTalk  DingTalkConfig  `yaml:"dingtalk"`
	LLM       LLMConfig       `yaml:"llm"`
	App       AppConfig       `yaml:"app"`
	AI        AIConfig        `yaml:"ai"`
}

type DatabaseConfig struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	User     string `yaml:"user"`
	Password string `yaml:"password"`
	Name     string `yaml:"name"`
}

func (d *DatabaseConfig) DSN() string {
	return fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		d.Host, d.Port, d.User, d.Password, d.Name)
}

type StarRocksConfig struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	User     string `yaml:"user"`
	Password string `yaml:"password"`
	Database string `yaml:"database"`
}

func (s *StarRocksConfig) DSN() string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4",
		s.User, s.Password, s.Host, s.Port, s.Database)
}

type DingTalkConfig struct {
	Webhook string `yaml:"webhook"`
	Secret  string `yaml:"secret"`
}

type LLMConfig struct {
	DefaultProvider string `yaml:"default_provider"`
}

type AppConfig struct {
	Host         string `yaml:"host"`
	Port         int    `yaml:"port"`
	JWTSecret    string `yaml:"jwt_secret"`
	JWTExpire    int    `yaml:"jwt_expire"`
	RefreshExpire int   `yaml:"refresh_expire"`
}

type AIConfig struct {
	Host string `yaml:"host"`
	Port int    `yaml:"port"`
}

var cfg *Config

func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("读取配置文件失败: %w", err)
	}

	cfg = &Config{}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("解析配置文件失败: %w", err)
	}

	return cfg, nil
}

func Get() *Config {
	return cfg
}
