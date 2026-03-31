package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Database  DatabaseConfig  `yaml:"database"`
	Redis     RedisConfig     `yaml:"redis"`
	StarRocks StarRocksConfig `yaml:"starrocks"`
	DingTalk  DingTalkConfig  `yaml:"dingtalk"`
	LLM       LLMConfig       `yaml:"llm"`
	App       AppConfig       `yaml:"app"`
	AI        AIConfig        `yaml:"ai"`
	Logging   LoggingConfig   `yaml:"logging"`
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

type RedisConfig struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	Password string `yaml:"password"`
	DB       int    `yaml:"db"`
}

func (r *RedisConfig) Addr() string {
	return fmt.Sprintf("%s:%d", r.Host, r.Port)
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

type LoggingConfig struct {
	Level    string `yaml:"level"`    // debug/info/warn/error
	Format   string `yaml:"format"`   // json/text
	Output   string `yaml:"output"`   // file/stdout/both
	MaxSize  int    `yaml:"max_size"` // MB per file
	MaxAge   int    `yaml:"max_age"`  // days to retain
	Compress bool   `yaml:"compress"` // compress old logs
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
