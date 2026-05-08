package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"time"

	"dev_metric/config"

	"github.com/redis/go-redis/v9"
)

var client *redis.Client

// Init 初始化 Redis 连接
func Init(cfg *config.RedisConfig) error {
	client = redis.NewClient(&redis.Options{
		Addr:     cfg.Addr(),
		Password: cfg.Password,
		DB:       cfg.DB,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("Redis 连接失败: %w", err)
	}

	return nil
}

// Get 获取 Redis 客户端
func Get() *redis.Client {
	return client
}

// Close 关闭连接
func Close() error {
	if client != nil {
		return client.Close()
	}
	return nil
}

// GetJSON 从 Redis 获取 JSON 数据
func GetJSON(ctx context.Context, key string, dest interface{}) error {
	val, err := client.Get(ctx, key).Result()
	if err != nil {
		return err
	}
	return json.Unmarshal([]byte(val), dest)
}

// SetJSON 设置 JSON 数据到 Redis，带随机过期 jitter
func SetJSON(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}

	// 添加随机 jitter: 0-60秒，避免惊群
	jitter := time.Duration(rand.Intn(60)) * time.Second
	actualTTL := ttl + jitter

	return client.Set(ctx, key, data, actualTTL).Err()
}

// Delete 删除 key
func Delete(ctx context.Context, key string) error {
	return client.Del(ctx, key).Err()
}

// DeletePattern 删除匹配的所有 key
func DeletePattern(ctx context.Context, pattern string) error {
	iter := client.Scan(ctx, 0, pattern, 0).Iterator()
	for iter.Next(ctx) {
		if err := client.Del(ctx, iter.Val()).Err(); err != nil {
			return err
		}
	}
	return iter.Err()
}

// MetricDataKey 生成指标数据缓存 key
func MetricDataKey(metricID uint) string {
	return fmt.Sprintf("metric:data:%d", metricID)
}

// AlertRuleDataKey 生成告警规则数据缓存 key
func AlertRuleDataKey(ruleID uint) string {
	return fmt.Sprintf("alert:data:%d", ruleID)
}
