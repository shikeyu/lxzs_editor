import mysql.connector
import toml

def create_connection():
    with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
        secrets = toml.load(f)
    
    return mysql.connector.connect(
        host=secrets['mysql']['host'],
        user=secrets['mysql']['user'],
        password=secrets['mysql']['password'],
        database=secrets['mysql']['database']
    )

def init_db():
    conn = create_connection()
    cursor = conn.cursor()

    # Create ai_config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(100) UNIQUE NOT NULL,
            config_value TEXT,
            description VARCHAR(255),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    # Create glossaries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS glossaries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            table_name VARCHAR(100) NOT NULL,
            source_term VARCHAR(255) NOT NULL,
            target_term VARCHAR(255) NOT NULL,
            notes TEXT,
            created_by VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_term_per_table (table_name, source_term)
        )
    """)

    # Create translation_history table (cache)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translation_cache (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source_hash VARCHAR(64) UNIQUE NOT NULL,
            source_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            model_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert default config if not exists
    default_configs = [
        ('api_endpoint', 'https://dashscope.aliyuncs.com/compatible-mode/v1', '阿里百炼API地址'),
        ('model_name', 'qwen-plus', '使用的模型名称'),
        ('prompt_template', '你是一个专业的日文游戏本地化翻译人员。请将以下日文游戏文本翻译成中文。\\n翻译要求：\\n1. 保持原意，自然流畅\\n2. 遵循游戏设定\\n{glossary_text}', '翻译系统提示词'),
        ('api_key_encrypted', '', '加密的API Key'),
        ('encryption_key', '', '用于加解密的本地密钥（实际使用中应放在环境变量或secrets中，此处仅作备用机制）')
    ]

    for key, val, desc in default_configs:
        cursor.execute("""
            INSERT IGNORE INTO ai_config (config_key, config_value, description)
            VALUES (%s, %s, %s)
        """, (key, val, desc))

    conn.commit()
    cursor.close()
    conn.close()
    print("Database tables initialized successfully.")

if __name__ == "__main__":
    init_db()
