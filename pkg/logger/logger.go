package logger

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/natefinch/lumberjack"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/pkgerrors"

	"dev_metric/config"
)

var Log zerolog.Logger

// Init 初始化全局日志器
func Init(cfg *config.LoggingConfig) {
	// 设置 zerolog 配置
	zerolog.ErrorStackMarshaler = pkgerrors.MarshalStack
	zerolog.TimeFieldFormat = time.RFC3339Nano

	// 解析日志级别
	level := parseLevel(cfg.Level)
	zerolog.SetGlobalLevel(level)

	// 确定输出
	var writers []io.Writer

	// 文件输出
	if cfg.Output == "file" || cfg.Output == "both" {
		logFile := getLogFilename()
		fileWriter := &lumberjack.Logger{
			Filename:   logFile,
			MaxSize:    cfg.MaxSize,
			MaxAge:     cfg.MaxAge,
			MaxBackups: 0, // 保留全部，不自动删除
			Compress:   cfg.Compress,
		}
		writers = append(writers, fileWriter)
	}

	// 标准输出
	if cfg.Output == "stdout" || cfg.Output == "both" {
		writers = append(writers, os.Stdout)
	}

	// 如果没有配置任何输出，默认输出到 stdout
	if len(writers) == 0 {
		writers = append(writers, os.Stdout)
	}

	// 创建 multi-writer
	var writer io.Writer
	if len(writers) == 1 {
		writer = writers[0]
	} else {
		writer = io.MultiWriter(writers...)
	}

	// 设置日志格式
	if cfg.Format == "text" {
		writer = zerolog.ConsoleWriter{Out: writer}
	}

	// 初始化全局日志器
	Log = zerolog.New(writer).With().Timestamp().Caller().Logger()
}

// getLogFilename 获取日志文件名（按日期）
func getLogFilename() string {
	logDir := "logs"
	// 确保目录存在
	if err := os.MkdirAll(logDir, 0755); err != nil {
		fmt.Printf("警告: 创建日志目录失败: %v，使用 stderr\n", err)
		return "app.log"
	}
	filename := fmt.Sprintf("app-%s.log", time.Now().Format("2006-01-02"))
	return filepath.Join(logDir, filename)
}

// parseLevel 解析日志级别字符串
func parseLevel(level string) zerolog.Level {
	switch strings.ToLower(level) {
	case "debug":
		return zerolog.DebugLevel
	case "info":
		return zerolog.InfoLevel
	case "warn", "warning":
		return zerolog.WarnLevel
	case "error":
		return zerolog.ErrorLevel
	case "fatal":
		return zerolog.FatalLevel
	default:
		return zerolog.InfoLevel
	}
}

// Info 记录信息日志
func Info() *zerolog.Event {
	return Log.Info()
}

// Debug 记录调试日志
func Debug() *zerolog.Event {
	return Log.Debug()
}

// Warn 记录警告日志
func Warn() *zerolog.Event {
	return Log.Warn()
}

// Error 记录错误日志
func Error() *zerolog.Event {
	return Log.Error()
}

// Fatal 记录致命错误日志
func Fatal() *zerolog.Event {
	return Log.Fatal()
}

// WithField 添加单个字段
func WithField(key string, value interface{}) zerolog.Logger {
	return Log.With().Interface(key, value).Logger()
}

// WithFields 添加多个字段
func WithFields(fields map[string]interface{}) zerolog.Logger {
	ctx := Log.With()
	for k, v := range fields {
		ctx = ctx.Interface(k, v)
	}
	return ctx.Logger()
}
