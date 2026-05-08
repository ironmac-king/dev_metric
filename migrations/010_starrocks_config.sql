-- StarRocks 配置表
CREATE TABLE IF NOT EXISTS starrocks_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    host VARCHAR(128) NOT NULL,
    port INT NOT NULL DEFAULT 9030,
    "user" VARCHAR(64) NOT NULL,
    password VARCHAR(256),
    database VARCHAR(64) NOT NULL,
    timeout INT DEFAULT 10,
    query_timeout INT DEFAULT 30,
    is_active SMALLINT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
