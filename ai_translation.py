import streamlit as st
import mysql.connector
from mysql.connector import Error
import json
import requests
import base64
from cryptography.fernet import Fernet
import pandas as pd
import io
import time

# --- Database Connection ---
def create_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# --- Encryption ---
def get_encryption_key():
    """获取或生成加密密钥，保存在数据库中以保证持久化"""
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT config_value FROM ai_config WHERE config_key = 'encryption_key'")
        result = cursor.fetchone()
        
        if result and result['config_value']:
            key = result['config_value'].encode('utf-8')
        else:
            key = Fernet.generate_key()
            cursor.execute("UPDATE ai_config SET config_value = %s WHERE config_key = 'encryption_key'", (key.decode('utf-8'),))
            conn.commit()
            
        return key
    except Error as e:
        st.error(f"DB Error (get_encryption_key): {e}")
        return Fernet.generate_key() # Fallback
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def encrypt_data(data):
    if not data: return ""
    f = Fernet(get_encryption_key())
    return f.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_data(data):
    if not data: return ""
    try:
        f = Fernet(get_encryption_key())
        return f.decrypt(data.encode('utf-8')).decode('utf-8')
    except Exception as e:
        return ""

# --- Config Management ---
def get_ai_config(key):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT config_value FROM ai_config WHERE config_key = %s", (key,))
        result = cursor.fetchone()
        return result['config_value'] if result else ""
    except Error as e:
        st.error(f"DB Error (get_ai_config): {e}")
        return ""
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def set_ai_config(key, value):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_config (config_key, config_value) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE config_value = %s
        """, (key, value, value))
        conn.commit()
    except Error as e:
        st.error(f"DB Error (set_ai_config): {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

# --- Glossary Management ---
def get_glossary(table_name):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM glossaries WHERE table_name = %s OR table_name = 'global' ORDER BY id DESC", (table_name,))
        return cursor.fetchall()
    except Error as e:
        st.error(f"DB Error (get_glossary): {e}")
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def add_glossary_term(table_name, source, target, notes, user):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO glossaries (table_name, source_term, target_term, notes, created_by)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE target_term=%s, notes=%s
        """, (table_name, source, target, notes, user, target, notes))
        conn.commit()
        return True
    except Error as e:
        st.error(f"添加词汇失败: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def delete_glossary_term(term_id):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM glossaries WHERE id = %s", (term_id,))
        conn.commit()
        return True
    except Error as e:
        st.error(f"删除词汇失败: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

# --- Core AI Call ---
def call_dashscope_api(text_lines, glossary_list):
    api_key_enc = get_ai_config('api_key_encrypted')
    api_key = decrypt_data(api_key_enc)
    
    # 兼容从 secrets.toml 直接读取
    if not api_key and "api_key" in st.secrets and "ali_api_key" in st.secrets["api_key"]:
        api_key = st.secrets["api_key"]["ali_api_key"]

    if not api_key:
        return False, "API Key 未配置，请在设置中配置。"

    endpoint = get_ai_config('api_endpoint') or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = get_ai_config('model_name') or "qwen-plus"
    template = get_ai_config('prompt_template') or "你是一个专业的日文游戏本地化翻译人员。请将以下日文文本翻译成中文。\\n{glossary_text}"

    # Build Glossary Text
    glossary_text = ""
    if glossary_list:
        glossary_text = "请参考以下专业词汇对照表进行翻译：\n"
        for g in glossary_list:
            glossary_text += f"- {g['source_term']} -> {g['target_term']} ({g.get('notes', '')})\n"

    system_prompt = template.replace("{glossary_text}", glossary_text)

    user_content = f"""
请严格按要求翻译以下文本数组。
要求：
1. 必须返回合法的 JSON 格式。
2. 返回的 JSON 必须是一个数组，数组长度必须与输入数组完全一致（即必须返回 {len(text_lines)} 个字符串元素）。
3. 数组中的每一项对应输入数组中相同位置的翻译结果。
4. 【极其重要】绝对不要遗漏任何一行，也绝对不要把几行合并成一行！即使有些行看似无意义（如只包含符号或占位符），也请照样保留原样并作为独立的数组元素返回。
5. 保持原文中的特殊控制符（如 {{CD}}, {{CE}}, {{D1}}, {{D5}} 等）原样输出，并将它们放置在译文中对应词汇的正确位置。

输入数组（共 {len(text_lines)} 行）：
{json.dumps(text_lines, ensure_ascii=False)}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(f"{endpoint}/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        res_json = response.json()
        
        content = res_json['choices'][0]['message']['content']
        # Try parsing JSON array
        try:
            translated_lines = json.loads(content)
            if isinstance(translated_lines, dict):
                # 某些模型可能返回 {"translated": [...]}
                for k, v in translated_lines.items():
                    if isinstance(v, list):
                        translated_lines = v
                        break
                        
            if not isinstance(translated_lines, list):
                return False, f"API 返回的格式不是数组: {content}"
                
            if len(translated_lines) != len(text_lines):
                return False, f"翻译行数不匹配: 输入 {len(text_lines)} 行，返回 {len(translated_lines)} 行。"
                
            return True, translated_lines
        except json.JSONDecodeError:
            return False, f"无法解析 API 返回的 JSON: {content}"

    except Exception as e:
        return False, f"API 请求失败: {str(e)}"

# --- Cache ---
def get_cached_translation(source_hash):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT translated_text FROM translation_cache WHERE source_hash = %s", (source_hash,))
        res = cursor.fetchone()
        return res['translated_text'] if res else None
    except:
        return None

def set_cached_translation(source_hash, source_text, translated_text, model):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO translation_cache (source_hash, source_text, translated_text, model_name)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE translated_text=%s
        """, (source_hash, source_text, translated_text, model, translated_text))
        conn.commit()
    except:
        pass
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

# --- UI Components ---
def render_ai_settings():
    st.header("AI 翻译配置管理")
    
    with st.form("ai_settings_form"):
        # Load existing config
        current_endpoint = get_ai_config('api_endpoint')
        current_model = get_ai_config('model_name')
        current_template = get_ai_config('prompt_template')
        
        # Determine current api key masked
        enc_key = get_ai_config('api_key_encrypted')
        api_key_placeholder = "********" if enc_key else ""
        
        new_api_key = st.text_input("阿里百炼 API Key", type="password", placeholder=api_key_placeholder)
        new_endpoint = st.text_input("API Endpoint", value=current_endpoint)
        new_model = st.text_input("模型名称", value=current_model)
        new_template = st.text_area("提示词模板", value=current_template, height=150)
        
        st.caption("提示：在提示词中使用 `{glossary_text}` 来表示词汇表插入位置。")
        st.caption("注意：您的 API Key 将被自动加密后安全地存储在数据库中，不会以明文形式保存。")
        
        if st.form_submit_button("保存配置"):
            if new_api_key:
                set_ai_config('api_key_encrypted', encrypt_data(new_api_key))
            set_ai_config('api_endpoint', new_endpoint)
            set_ai_config('model_name', new_model)
            set_ai_config('prompt_template', new_template)
            st.success("配置已保存！")

def render_glossary_management(table_name):
    st.header(f"词汇对照表管理 ({table_name})")
    
    # 导入/导出
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("导入词汇表")
        uploaded_file = st.file_uploader("上传 CSV/TSV 文件 (支持逗号或Tab分隔)", type=["csv", "tsv", "txt"])
        if uploaded_file and st.button("执行导入"):
            try:
                # 尝试读取，如果是制表符分割的也兼容
                # 通过 sniffing 或是直接尝试两种常见的分隔符
                file_content = uploaded_file.getvalue()
                # 重置指针
                uploaded_file.seek(0)
                
                # 简单判断是否包含制表符，如果包含大量制表符则假定为 tab 分割
                first_line = file_content.decode('utf-8', errors='ignore').split('\n')[0]
                sep = '\t' if '\t' in first_line else ','
                
                # 尝试解析带表头的，如果失败或列名不对，则使用无表头模式
                df = pd.read_csv(uploaded_file, sep=sep)
                
                # 检查是否包含预期的列名
                if '原文' not in df.columns or '译文' not in df.columns:
                    # 如果没有列名，则认为文件没有表头，前两列分别是原文和译文
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=sep, header=None)
                    # 重命名列以便后续处理
                    if len(df.columns) >= 2:
                        df.rename(columns={0: '原文', 1: '译文'}, inplace=True)
                        if len(df.columns) >= 3:
                            df.rename(columns={2: '备注'}, inplace=True)
                    else:
                        raise ValueError("文件至少需要包含原文和译文两列")
                
                success_count = 0
                for _, row in df.iterrows():
                    if pd.notna(row.get('原文')) and pd.notna(row.get('译文')):
                        add_glossary_term(table_name, str(row['原文']), str(row['译文']), str(row.get('备注', '')), st.session_state.get('username', 'system'))
                        success_count += 1
                st.success(f"成功导入 {success_count} 条词汇！")
            except Exception as e:
                st.error(f"导入失败: {e}")
                
    with col2:
        st.subheader("导出词汇表")
        glossary_list = get_glossary(table_name)
        if glossary_list:
            df_export = pd.DataFrame(glossary_list)
            df_export = df_export.rename(columns={'source_term': '原文', 'target_term': '译文', 'notes': '备注'})
            
            # 提供两种格式的下载
            csv = df_export[['原文', '译文', '备注']].to_csv(index=False).encode('utf-8-sig')
            tsv = df_export[['原文', '译文', '备注']].to_csv(index=False, sep='\t').encode('utf-8-sig')
            
            st.download_button("下载为 CSV (逗号分隔)", data=csv, file_name=f"glossary_{table_name}.csv", mime="text/csv")
            st.download_button("下载为 TSV (Tab分隔)", data=tsv, file_name=f"glossary_{table_name}.tsv", mime="text/tab-separated-values")
    
    st.divider()
    
    # 添加新词汇
    with st.form("add_term_form"):
        st.subheader("添加/更新词汇")
        c1, c2, c3 = st.columns(3)
        source_term = c1.text_input("原文 (日文)*")
        target_term = c2.text_input("译文 (中文)*")
        notes = c3.text_input("备注 (选填)")
        if st.form_submit_button("保存"):
            if source_term and target_term:
                if add_glossary_term(table_name, source_term, target_term, notes, st.session_state.get('username', 'system')):
                    st.success("保存成功！")
                    st.rerun()
            else:
                st.error("原文和译文不能为空！")
                
    # 搜索与列表展示
    st.subheader("当前词汇列表")
    search_q = st.text_input("🔍 搜索词汇")
    filtered_list = [g for g in glossary_list if search_q.lower() in g['source_term'].lower() or search_q.lower() in g['target_term'].lower()] if search_q else glossary_list
    
    if filtered_list:
        for term in filtered_list:
            with st.expander(f"{term['source_term']} ➡️ {term['target_term']}"):
                st.write(f"**备注:** {term['notes']}")
                st.write(f"**创建者:** {term['created_by']}")
                if st.button("删除", key=f"del_term_{term['id']}"):
                    if delete_glossary_term(term['id']):
                        st.success("已删除")
                        time.sleep(0.5)
                        st.rerun()
    else:
        st.info("暂无匹配词汇。")

