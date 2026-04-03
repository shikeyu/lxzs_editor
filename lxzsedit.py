import streamlit as st
import mysql.connector
import bcrypt
from mysql.connector import Error
from datetime import datetime
import time
import streamlit.components.v1 as components

# 连接到远端 MySQL 数据库
def create_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# 校对用户名和密码
def validate_user(username, password):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT password FROM Users WHERE username = %s", (username,))
        result = cursor.fetchone()
        if result and bcrypt.checkpw(password.encode('utf-8'), result['password'].encode('utf-8')):
            return True
        return False
    except Error as e:
        st.error(f"Error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 更新用户的 lastlogin 字段
def update_last_login(username):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE Users SET lastlogin = %s WHERE username = %s", (now, username))
        conn.commit()
    except Error as e:
        st.error(f"Error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 读取文件列表
def get_filelist():
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tablelist")
        result = cursor.fetchall()
        return result
    except Error as e:
        st.error(f"Error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 读取数据表ID列表
@st.cache_data
def get_table_id(fname):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT ID FROM `{fname}`")
        result = cursor.fetchall()
        return result
    except Error as e:
        st.error(f"Error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 向前查找包含指定字符的数据ID
def get_id_up(fname,s_id,s_text,f_text):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT max(ID) as get_id FROM `{fname}` WHERE `{f_text}` LIKE %s AND ID < %s"
        cursor.execute(query, (f"%{s_text}%", s_id))
        result = cursor.fetchone()
        return result['get_id'] if result else None
    except Error as e:
        st.error("查找过程中出错。")
        return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            
# 向后查找包含指定字符的数据ID
def get_id_down(fname, s_id, s_text, f_text):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT min(ID) as get_id FROM `{fname}` WHERE `{f_text}` LIKE %s AND ID > %s"
        cursor.execute(query, (f"%{s_text}%", s_id))
        result = cursor.fetchone()
        return result['get_id'] if result else None
    except Error as e:
        st.error("查找过程中出错。")
        return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            

# 读取数据表指定ID内容
def get_table_data(fname,id):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT * FROM `{fname}` WHERE ID = %s"
        cursor.execute(query, (id,))
        result = cursor.fetchall()
        return result
    except Error as e:
        st.error(f"Error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# 更新记录
def update_record(fname, record_id, ctext, editor):
    if editor == 'guest':
        return False, "演示用户无权更新数据！"

    try:
        conn = create_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f"UPDATE `{fname}` SET ctext = %s, editor = %s, update_time = %s WHERE id = %s", (ctext, editor, now, record_id))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "译文保存成功!"
        else:
            return False, "没有数据被更新，可能是因为内容没有变化。"
    except Error as e:
        return False, f"保存失败: {e}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# 输入文本检测
def validate_string(s):
    # 用于存放括号的栈
    stack = []
    
    # 遍历字符串
    i = 0
    while i < len(s):
        if s[i] == '{':
            if not stack or stack[-1] in ['[WAIT]', '[ENTER]','[NAME1]','[NAME2]']:
                stack.append('{')
            else:
                print(stack[-1])
                return False
        elif s[i] == '}':
            if not stack or stack[-1] != '{':
                return False
            stack.pop()
        elif s[i] == '[':
            # 检查特殊字符串 "[WAIT]" 或 "[ENTER]"
            if s[i:i+6] == '[WAIT]':
                stack.append('[WAIT]')
                i += 5  # 跳过 "[WAIT]"
            elif s[i:i+7] in ['[ENTER]','[NAME1]','[NAME2]']:
                stack.append(s[i:i+7])
                i += 6  # 跳过 "[ENTER]"等
            else:
                return False
        elif s[i] == ']':
            if not stack or stack[-1] not in ['[WAIT]', '[ENTER]','[NAME1]','[NAME2]']:
                return False
            stack.pop()
        
        i += 1
    
    return True

# 将带控制符文本转换为显示文本

def display_text(intext):
    # 定义kzfdzb的替换规则
    kzfdzb = [
        {"okzf": "{D5 00 08 00 }", "nkzf": "[NAME1]"},
        {"okzf": "{D5 00 09 00 }", "nkzf": "[NAME2]"},
        {"okzf": "{CC 00 00 00 }", "nkzf": "[ENTER]"},
        {"okzf": "{CC 00 01 03 }", "nkzf": "[WAIT]"},
    ]

    yw1 = intext.replace("\r\n", "\n")
    display_text = ""
    viewtext = ""

    # 替换kzfdzb中的nkzf为对应的okzf
    for i in range(4):
        yw1 = yw1.replace(kzfdzb[i]["nkzf"], kzfdzb[i]["okzf"])
    yw1 = yw1.replace("{FF}","\n{CC 00 00 00 }\n")

    allyw = yw1.split("\n")
    # 为了防止行级错乱，我们需要根据 {03...} 和 {04...} 来进行分组提取
    # 但 display_text 原本是将整个文本返回。
    for ls in allyw:
        if ls.startswith("{"):
            if ls.startswith("{79"):  # 添加选择项
                display_text += ls[19:-1] + "\n"
            elif ls.startswith("{23"):  # 添加未知项
              display_text += ls[10:-1] + "\n"
            elif ls.startswith("{D9"):  # 添加未知项
                viewtext += "＃"
            elif ls == "{D5 00 08 00 }":
                viewtext += "风海"
            elif ls == "{D5 00 09 00 }":  # 添加姓名
                viewtext += "纯也"
            elif ls.startswith("{D5 00 "):  # 添加姓名
                viewtext += "{D5}" # 简化控制符
            elif ls.startswith("{D1 07"):  # 添加关键词
                viewtext += "{D1}" # 简化控制符
            elif ls.startswith("{CD "):  # 特殊属性控制符起始
                viewtext += "{CD}" # 简化控制符
            elif ls.startswith("{CE "):  # 特殊属性控制符结束
                viewtext += "{CE}" # 简化控制符
            elif (ls in ["{CC 00 00 00 }", "{CC 00 01 00 }", "{04 00 }", "{69 00 }", "{75 00 }"]) or ls.startswith("{CC 00 ") or ls.startswith("{75 00 ") or ls.startswith("{03 "):
                # 当遇到翻页符 {04...} 或者 对话分组符 {03...} 时，强制结束当前 viewtext 的合并并换行
                display_text += viewtext + "\n"
                viewtext = ""
                if ls.startswith("{04 ") or ls.startswith("{03 "):
                    display_text += viewtext + "\n"
            elif ls.startswith("{87}"): #添加姓名编码
                viewtext += ls
            else:
                # 其他未识别的控制符，为了避免丢失导致分段错误，我们将其转换为一个占位符，
                # 这样它可以被提取并被AI看到，同时也能保持 tokens 的行级对应关系
                pass
        elif not ls.startswith("#"):  #去除注释行
            viewtext += ls

    if viewtext:
        display_text += viewtext + "\n"

    return display_text

def script_replace_old(jtext, vtext):
    """
    将jtext的值用display_text函数除去控制符，然后去除不含字符的空行后放入sour数组，
    再将vtext的值去除空行后放入dest数组，判断两个数组的长度，
    长度相同进行后续替换操作。将jtext的值逐条用sour中的值替换为dest对应的值，然后返回。
    
    参数:
        jtext (str): 原始日文文本，包含控制符
        vtext (str): 译文，不包含控制符
        
    返回:
        tuple: (成功标志, 结果文本或错误信息)
    """
    import streamlit as st
    import re
    
    # 使用display_text函数处理jtext以去除控制符
    cleaned_jtext = display_text(jtext)
    
    # 将处理后的jtext按行分割并去除空行，存入sour数组
    sour = [line for line in cleaned_jtext.split('\n') if line.strip()]
    
    # 将vtext按行分割并去除空行，存入dest数组
    dest = [line for line in vtext.split('\n') if line.strip()]
    
    # 判断两个数组的长度是否相同
    if len(sour) != len(dest):
        return False, f"源文本行数({len(sour)})与译文行数({len(dest)})不匹配，无法进行替换。"
        
    # 显示调试信息
    with st.expander("替换详情"):
        st.write(f"源文本行数: {len(sour)}")
        st.write(f"译文行数: {len(dest)}")
        st.write("源文本与译文对照:")
        for i in range(len(sour)):
            st.write(f"源文本[{i}]: {sour[i]}")
            st.write(f"译文[{i}]: {dest[i]}")
            st.write("---")
    
    # 获取原始jtext中的所有控制符和文本
    # 提取控制符和文本内容
    pattern = r'(\{[^\}]+\}|[^\{]+)'
    tokens = re.findall(pattern, jtext)
    
    # 创建映射表，将清理后的文本映射到原始文本
    text_mapping = {}
    for i, line in enumerate(sour):
        text_mapping[line] = dest[i]
    
    # 处理每个token，如果是文本且在映射表中，则替换
    result = ""
    for token in tokens:
        if token.startswith('{') and token.endswith('}'): 
            # 这是控制符，保持不变
            result += token
        else:
            # 这是文本，检查是否需要替换
            # 先检查完整token是否在映射表中
            token_stripped = token.strip()
            if token_stripped and token_stripped in text_mapping:
                # 保持原始的前导和尾随空白
                leading_spaces = ""
                trailing_spaces = ""
                
                # 计算前导空白
                for char in token:
                    if char.isspace():
                        leading_spaces += char
                    else:
                        break
                        
                # 计算尾随空白
                for char in reversed(token):
                    if char.isspace():
                        trailing_spaces = char + trailing_spaces
                    else:
                        break
                        
                result += leading_spaces + text_mapping[token_stripped] + trailing_spaces
            else:
                # 如果完整token不在映射表中，尝试按行分割并逐行替换
                lines = token.split('\n')
                processed_lines = []
                
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped and line_stripped in text_mapping:
                        # 保持原始的前导和尾随空白
                        leading_spaces = ""
                        trailing_spaces = ""
                        
                        # 计算前导空白
                        for char in line:
                            if char.isspace():
                                leading_spaces += char
                            else:
                                break
                                
                        # 计算尾随空白
                        for char in reversed(line):
                            if char.isspace():
                                trailing_spaces = char + trailing_spaces
                            else:
                                break
                                
                        processed_lines.append(leading_spaces + text_mapping[line_stripped] + trailing_spaces)
                    else:
                        processed_lines.append(line)
                        
                result += '\n'.join(processed_lines)
    
    return True, result



def script_replace(jtext, vtext):
    """
    将jtext的值用display_text函数除去控制符，然后去除不含字符的空行后放入sour数组，
    再将vtext的值去除空行后放入dest数组，判断两个数组的长度，
    长度相同进行后续替换操作。将jtext的值逐条用sour中的值替换为dest对应的值，然后返回。
    
    参数:
        jtext (str): 原始日文文本，包含控制符
        vtext (str): 译文，不包含控制符
        
    返回:
        tuple: (成功标志, 结果文本或错误信息)
    """
    import streamlit as st
    import re
    
    # 将vtext按行分割并去除空行，存入dest数组
    dest = [line.strip() for line in vtext.split('\n') if line.strip()]
    
    # 严格按照控制符拆分 jtext。偶数索引为纯文本（可能含空白），奇数索引为控制符。
    tokens = re.split(r'(\{[^\{\}]+\})', jtext)
    
    # 模拟 display_text 的逻辑，将 tokens 分组为“逻辑行”
    logical_lines = []
    current_line = []
    
    for i, token in enumerate(tokens):
        if i % 2 == 1: # 控制符
            if token.startswith("{79") or token.startswith("{23"):
                if current_line:
                    logical_lines.append(current_line)
                    current_line = []
                logical_lines.append([i])
            elif (token in ["{CC 00 00 00 }", "{CC 00 01 00 }", "{04 00 }", "{69 00 }", "{75 00 }"] or 
                  token.startswith("{CC 00 ") or token.startswith("{75 00 ") or token.startswith("{03 ")):
                if current_line:
                    logical_lines.append(current_line)
                    current_line = []
            else:
                current_line.append(i)
        else: # 纯文本
            current_line.append(i)
            
    if current_line:
        logical_lines.append(current_line)

    # 过滤出真正产生可见文本的逻辑行
    valid_logical_lines = []
    for ll in logical_lines:
        viewtext = ""
        for i in ll:
            token = tokens[i]
            if i % 2 == 1:
                if token.startswith("{79"): viewtext += token[19:-1]
                elif token.startswith("{23"): viewtext += token[10:-1]
                elif token.startswith("{D9"): viewtext += "＃"
                elif token == "{D5 00 08 00 }": viewtext += "风海"
                elif token == "{D5 00 09 00 }": viewtext += "纯也"
                elif token.startswith("{D5 00 "): viewtext += "{D5}"
                elif token.startswith("{D1 07"): viewtext += "{D1}"
                elif token.startswith("{CD "): viewtext += "{CD}"
                elif token.startswith("{CE "): viewtext += "{CE}"
                elif token.startswith("{87}"): viewtext += token
            else:
                lines = token.replace("\r\n", "\n").split("\n")
                for ls in lines:
                    if not ls.startswith("#"):
                        viewtext += ls
        if viewtext.strip():
            valid_logical_lines.append(ll)

    # 判断有效行数是否与译文行数一致
    if len(valid_logical_lines) != len(dest):
        # 为了调试和查看，我们可以把解析出来的原文行打印出来
        sour_preview = []
        for ll in valid_logical_lines:
            viewtext = ""
            for i in ll:
                token = tokens[i]
                if i % 2 == 1:
                    if token.startswith("{79"): viewtext += token[19:-1]
                    elif token.startswith("{23"): viewtext += token[10:-1]
                    elif token.startswith("{D9"): viewtext += "＃"
                    elif token == "{D5 00 08 00 }": viewtext += "风海"
                    elif token == "{D5 00 09 00 }": viewtext += "纯也"
                    elif token.startswith("{D5 00 "): viewtext += "{D5}"
                    elif token.startswith("{D1 07"): viewtext += "{D1}"
                    elif token.startswith("{CD "): viewtext += "{CD}"
                    elif token.startswith("{CE "): viewtext += "{CE}"
                    elif token.startswith("{87}"): viewtext += token
                else:
                    lines = token.replace("\r\n", "\n").split("\n")
                    for ls in lines:
                        if not ls.startswith("#"):
                            viewtext += ls
            sour_preview.append(viewtext.strip())
            
        with st.expander("替换详情 - 行数不匹配"):
            st.write(f"原文有效行数: {len(valid_logical_lines)}")
            st.write(f"译文有效行数: {len(dest)}")
            for idx, s in enumerate(sour_preview):
                st.write(f"原文[{idx}]: {s}")
            for idx, d in enumerate(dest):
                if idx < len(dest):
                    st.write(f"译文[{idx}]: {d}")
                
        return False, f"有效源文本行数({len(valid_logical_lines)})与译文行数({len(dest)})不匹配，无法进行精确替换。"

    # 执行替换
    inline_tags_pattern = r'(\{D5\}|\{D1\}|\{CD\}|\{CE\})'
    
    for ll, dest_line in zip(valid_logical_lines, dest):
        dest_parts = re.split(inline_tags_pattern, dest_line)
        dest_text_fragments = [p for p in dest_parts if p not in ['{D5}', '{D1}', '{CD}', '{CE}']]
        
        # 将逻辑行按行内控制符划分为多个片段
        segments = []
        current_seg = []
        for i in ll:
            if i % 2 == 1:
                token = tokens[i]
                is_inline = False
                if token.startswith("{D5 00 ") or token == "{D5 00 08 00 }" or token == "{D5 00 09 00 }":
                    is_inline = True
                elif token.startswith("{D1 07"):
                    is_inline = True
                elif token.startswith("{CD "):
                    is_inline = True
                elif token.startswith("{CE "):
                    is_inline = True
                    
                if is_inline:
                    segments.append(current_seg)
                    current_seg = []
                else:
                    current_seg.append(i)
            else:
                current_seg.append(i)
        segments.append(current_seg)
        
        # 如果 AI 破坏了行内控制符结构，导致片段数不一致，则进行降级回填
        if len(segments) != len(dest_text_fragments):
            fallback_text = re.sub(inline_tags_pattern, '', dest_line)
            dest_text_fragments = [fallback_text] + [''] * (len(segments) - 1)
            
        # 将译文片段填充回对应的片段中
        for seg, trans_frag in zip(segments, dest_text_fragments):
            best_idx = -1
            max_len = -1
            # 找到包含最多有效字符的文本块来承载译文
            for idx in seg:
                if idx % 2 == 0:
                    orig_text = tokens[idx]
                    m = re.match(r'^(\s*)(.*?)(\s*)$', orig_text, re.DOTALL)
                    if m:
                        core_len = len(m.group(2))
                        if core_len > max_len:
                            max_len = core_len
                            best_idx = idx
            
            # 如果没有找到任何可见字符，就随便选最后一个纯文本块
            if best_idx == -1:
                for idx in reversed(seg):
                    if idx % 2 == 0:
                        best_idx = idx
                        break
                        
            if best_idx != -1:
                for idx in seg:
                    if idx % 2 == 0:
                        orig_text = tokens[idx]
                        m = re.match(r'^(\s*)(.*?)(\s*)$', orig_text, re.DOTALL)
                        if m:
                            leading = m.group(1)
                            trailing = m.group(3)
                            if idx == best_idx:
                                tokens[idx] = leading + trans_frag + trailing
                            else:
                                tokens[idx] = leading + "" + trailing
            else:
                # 应对片段中全是控制符的情况（例如 {79} 标签本身）
                for idx in seg:
                    token = tokens[idx]
                    if token.startswith("{79"):
                        tokens[idx] = token[:19] + trans_frag + token[-1:]
                    elif token.startswith("{23"):
                        tokens[idx] = token[:10] + trans_frag + token[-1:]

    result = "".join(tokens)
    return True, result

# 获取所有留言及其跟帖
def get_messages_with_replies():
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 获取所有留言
    table = st.session_state.selected_table
    cursor.execute("SELECT * FROM messages WHERE tablename=%s ORDER BY created_at DESC",(table,))
    messages = cursor.fetchall()
    
    # 获取每条留言的跟帖
    for message in messages:
        cursor.execute("SELECT * FROM replies WHERE message_id = %s ORDER BY created_at ASC", (message['id'],))
        message['replies'] = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return messages

# 显示留言和跟帖
def display_messages(messages):
    with st.sidebar.container(height = 300 , border = True):
        for i, message in enumerate(messages):
            # 使用相同的背景色显示留言及其回复
            if i % 2 == 0:
                background_color = "#f0f0f0"  # 浅灰色背景
            else:
                background_color = "#ffffff"  # 白色背景
        
            # 显示留言
            st.markdown(
                f'<div style="background-color: {background_color}; padding: 2px; border-radius: 1px; margin-bottom: 1px; font-size: 11px;">'
                f'<strong>{message["username"]}</strong> 留言于 <code>{message["created_at"]}</code>:<br>'
                f'</div>'
                f'<div style="background-color: {background_color}; padding: 2px; border-radius: 1px; margin-bottom: 1px; font-size: 16px;">'
                f'{message["message"]}'
                f'</div>',
                unsafe_allow_html=True
            )
        
            # 显示跟帖（紧凑显示）
            #if message['replies']:
                #for reply in message['replies']:
                    #st.markdown(
                        #f'<div style="background-color: {background_color}; margin-left: 2px; padding: 5px; border-radius: 5px; margin-bottom: 5px; color: #555555;">'
                        #f'<strong>{reply["username"]}</strong> : {reply["reply"]}'
                        #f'</div>',
                        #unsafe_allow_html=True
                    #)
        
        # 在每条留言之间添加空行
        st.markdown("<br>", unsafe_allow_html=True)

# 插入留言
def insert_message(username, message):
    conn = create_connection()
    cursor = conn.cursor()
    table = st.session_state.selected_table
    query = "INSERT INTO messages (username, message, tablename) VALUES (%s, %s, %s)"
    cursor.execute(query, (username, message,table))
    conn.commit()
    cursor.close()
    conn.close()

# 登录界面
# 获取更新信息和最大版本号
def get_update_info():
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT version, update_info FROM update_logs ORDER BY version DESC")
        updates = cursor.fetchall()
        
        if not updates:
            return "无法获取更新信息", "1.0"
            
        # 获取最大版本号
        max_version = updates[0]['version']
        
        # 合并所有更新信息
        update_text = ""
        for update in updates:
            update_text += f"Version {update['version']}:\n{update['update_info']}\n\n"
        return update_text, max_version
    except Error as e:
        st.error(f"Error: {e}")
        return "无法获取更新信息", "1.0"
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def login_page():
    update_text, current_version = get_update_info()
    st.title(f"流行之神脚本编辑系统 {current_version}")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("登录"):
            if validate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                update_last_login(username)
                st.session_state.page = 'select_table'
                st.rerun()
            else:
                st.error("用户名或密码错误！！")
                time.sleep(2) 
    with col2:
        if st.button("修改密码"):
            st.session_state.page = 'change_password'
            st.rerun()

    # 显示更新信息
    st.text_area("更新日志", value=update_text, height=200, disabled=True)

# 密码修改界面
def change_password_page():
    st.title("修改密码")
    username = st.text_input("用户名")
    old_password = st.text_input("原密码", type="password")
    new_password = st.text_input("新密码", type="password")
    confirm_password = st.text_input("确认新密码", type="password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认修改"):
            if not username or not old_password or not new_password or not confirm_password:
                st.error("请填写所有字段！")
            elif new_password != confirm_password:
                st.error("两次输入的新密码不一致！")
            elif not validate_user(username, old_password):
                st.error("用户名或原密码错误！")
            else:
                if update_password(username, new_password):
                    st.success("密码修改成功！")
                    time.sleep(2)
                    st.session_state.page = 'login'
                    st.rerun()
                else:
                    st.error("密码修改失败，请稍后重试！")
    with col2:
        if st.button("返回登录"):
            st.session_state.page = 'login'
            st.rerun()

# 更新用户密码
def update_password(username, new_password):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        # 使用bcrypt加密新密码
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("UPDATE Users SET password = %s WHERE username = %s", (hashed_password, username))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        st.error(f"Error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# 获取用户权限
def get_user_permissions(username):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT t.table_name, t.title 
            FROM tablelist t
            JOIN user_table ut ON t.ID = ut.table_id
            JOIN Users u ON ut.user_id = u.Userid
            WHERE u.username = %s
        """, (username,))
        return cursor.fetchall()
    except Error as e:
        st.error(f"错误：{e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 表选择界面
def table_selection_page():
    st.title("请选择要修改的文本库")
    
    # 侧边栏：管理工具（仅 admin 可见）
    if st.session_state.get('username') == 'admin':
        st.sidebar.title("管理工具")
        if st.sidebar.button("AI 翻译配置"):
            st.session_state.page = 'ai_settings'
            st.rerun()
        if st.sidebar.button("用户管理"):
            st.session_state.page = 'user_admin'
            st.rerun()
    
    # 获取当前用户有权限的表
    user_tables = get_user_permissions(st.session_state.username)

    if not user_tables:
        st.warning("您没有权限编辑任何表格。")
        return

    # 生成简介列表及表映射
    table_mapping = {row['title']: row for row in user_tables}
    titles = [row['title'] for row in user_tables]

    selected_table = st.selectbox("文本库", titles)
    if st.button("打开数据表"):
        if selected_table:
            st.session_state.selected_table = table_mapping[selected_table]['table_name']
            st.session_state.selected_tabletitle = selected_table
            st.session_state.page = 'edit'
            st.rerun()
        else:
            st.warning("请选择要打开的表")

# 编辑界面
# 检查记录锁定状态
def check_lock(fname, record_id):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT locked_by, locked_time FROM `{fname}` WHERE id = %s", (record_id,))
        result = cursor.fetchone()
        
        if result['locked_by']:
            # 检查锁定是否过期（30分钟后自动解锁）
            if result['locked_time'] and (datetime.now() - result['locked_time']).total_seconds() > 1800:
                release_lock(fname, record_id)
                return None
            return result['locked_by']
        return None
    except Error as e:
        st.error(f"Error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 锁定记录
def lock_record(fname, record_id, username):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute(f"UPDATE `{fname}` SET locked_by = %s, locked_time = %s WHERE id = %s", 
                      (username, now, record_id))
        conn.commit()
        return True
    except Error as e:
        st.error(f"Error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 释放记录锁定
def release_lock(fname, record_id):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE `{fname}` SET locked_by = NULL, locked_time = NULL WHERE id = %s", 
                      (record_id,))
        conn.commit()
        return True
    except Error as e:
        st.error(f"Error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 在edit_page函数中修改相关代码
def edit_page():
    from ai_translation import call_dashscope_api, get_glossary, get_cached_translation, set_cached_translation
    import hashlib
    
    table = st.session_state.selected_table
    table_title = st.session_state.selected_tabletitle
    st.title(f"当前数据为: {table_title}")
    data_id = get_table_id(table)
    if not data_id:
        st.warning("No data found in the selected table.")
        return

    # 生成 ID 列表
    ids = [row['ID'] for row in data_id]

    if  'nowid' not in st.session_state:
        st.session_state.nowid = 0

    # 通过滑动条选择记录行
    selected_id = st.sidebar.slider("滑动滚动条选择记录", min_value=0, max_value=len(ids) - 1, value=st.session_state.nowid)
    if st.session_state.nowid != selected_id:
        st.session_state.need_replace = False
        if 'ctext' in st.session_state:
            del st.session_state.ctext
    st.session_state.nowid=selected_id
    
   
    b_up,b_down,b_input_id,b_goto=st.sidebar.columns(4, gap="small")
    button_up=b_up.button("◀️", help="上一条记录")
    button_down=b_down.button("▶️", help="下一条记录")
    input_id=b_input_id.number_input("跳转记录ID", min_value=0, max_value=len(ids) - 1, value=0, label_visibility="collapsed")
    button_goto=b_goto.button("🎯", help="跳转")
    
    # 跳转到指定记录
    if button_goto:
        if input_id >= 0 and input_id <= len(ids) - 1 and input_id != st.session_state.nowid:
            st.session_state.nowid=input_id
            if 'ctext' in st.session_state:
                del st.session_state.ctext
            st.rerun()

          
    # 查找功能按钮
    search_text = st.sidebar.text_input("查找译文")
    search_in=st.sidebar.radio("搜索范围",["原文","译文"],index=1,horizontal=1)
    s_up,s_down=st.sidebar.columns(2, gap="small")
    search_up=s_up.button("◀️向前查找")
    search_down=s_down.button("向后查找▶️")
    s_replace,s_rpbutton=st.sidebar.columns([0.70,0.30], gap="small")
    replace_text = s_replace.text_input("替换为",label_visibility="collapsed")
    do_replace=s_rpbutton.button("替换")
    Control_view=st.sidebar.checkbox("日文显示控制符", value=True)

    # 添加返回按钮
    if st.sidebar.button("返回选择界面"):
        # 返回前释放当前记录的锁定
        if 'previous_id' in st.session_state:
            release_lock(table, ids[st.session_state.previous_id])
        st.session_state.page = 'select_table'
        del st.session_state.nowid
        del st.session_state.selected_table
        if 'ctext' in st.session_state:
            del st.session_state.ctext
        if 'previous_id' in st.session_state:
            del st.session_state.previous_id
        st.rerun()
        
    st.sidebar.divider()
    if st.sidebar.button("📝 管理本表词汇"):
        st.session_state.page = 'glossary_mgmt'
        st.rerun()
    if st.sidebar.button("🔍 脚本冲突检测"):
        if 'previous_id' in st.session_state:
            release_lock(table, ids[st.session_state.previous_id])
        st.session_state.conflict_default_tables = [table]
        st.session_state.conflict_return_page = 'edit'
        st.session_state.page = 'conflict_analysis'
        st.rerun()
    
    # 获取所有留言及其跟帖
    #messages = get_messages_with_replies()

    # 显示留言和跟帖
    #display_messages(messages)
        
    #newchat=st.sidebar.chat_input(placeholder="您的留言。")

    # 更新留言
    #if newchat:
    #    insert_message(st.session_state.username,newchat)
    #    st.rerun()

    #显示上下条目
    if button_up:
        if st.session_state.nowid>0:
            st.session_state.nowid -=1
            if 'ctext' in st.session_state:
                del st.session_state.ctext
            st.rerun()
    if button_down:
        if st.session_state.nowid<len(ids) - 1:
            st.session_state.nowid +=1
            if 'ctext' in st.session_state:
                del st.session_state.ctext
            st.rerun()
  
    # 向前查找字符串
    if search_up and search_text:
        if search_in=='原文':
            found_id=get_id_up(table,ids[selected_id],search_text,'jtext')
        else:
            found_id=get_id_up(table,ids[selected_id],search_text,'ctext')
        if found_id:
            st.session_state.nowid=ids.index(found_id)
            if 'ctext' in st.session_state:
                del st.session_state.ctext
            st.rerun()
        
    #向后查找字符串
    if search_down and search_text:
        if search_in=='原文':
            found_id=get_id_down(table,ids[selected_id],search_text,'jtext')
        else:
            found_id=get_id_down(table,ids[selected_id],search_text,'ctext')
        if found_id:
            st.session_state.nowid=ids.index(found_id)
            if 'ctext' in st.session_state:
                del st.session_state.ctext
            st.rerun()
    

    data = get_table_data(table, ids[selected_id])
    if not data:
        st.warning("No data found in the selected table.")
        return
    record = data[0]

    if record:
        # 检查记录锁定状态
        if not ('ctext' in st.session_state): #记录有变动才检查锁定
            locked_by = check_lock(table, ids[selected_id])
            if locked_by and locked_by != st.session_state.username:
                st.warning(f"当前记录正在被用户 {locked_by} 编辑中，请稍后再试。")
                return
            elif not locked_by:
                lock_record(table, ids[selected_id], st.session_state.username)
            st.session_state.ctext = record['ctext']
            if 'temp_text' in st.session_state:
                del st.session_state.temp_text
        
        st.write("编号:", hex(record['ID']), "   编辑者:", record['editor'], "   更新时间:", record['update_time'])
        # 左右分两列
        s_left, s_right = st.columns(2, gap="small")
        
        if Control_view:
            s_left.text_area("日文", value=record['jtext'], height=200)
        else:
            s_left.text_area("日文", value=display_text(record['jtext']), height=200)  

        #查找替换字符串
        if do_replace and replace_text and search_text:
            st.session_state.ctext=st.session_state.ctext.replace(search_text,replace_text)
            
        # 编辑 ctext 字段
        st.session_state.newctext = s_left.text_area("译文", value=st.session_state.ctext, height=250)
           
        if ('temp_text' not in st.session_state): #初始化临时译文
            st.session_state.temp_text = display_text(st.session_state.ctext)
            
        vtext = s_right.text_area("模拟显示（也可用于存放临时翻译文本）", value=st.session_state.temp_text, height=500)
        # 将用户编辑后的文本同步回 session_state
        if vtext != st.session_state.temp_text:
            st.session_state.temp_text = vtext

        # 在右侧面板底部放置并排按钮
        st.markdown("---")
        # 创建三列用于并排放置按钮
        btn_col3,btn_col1, btn_col2 = s_right.columns(3)
        
        # 显示文本转译文
        if "{FF}" in st.session_state.ctext:
            if btn_col1.button("文本转换"):
                st.session_state.ctext=vtext.replace("\n","{FF}")
                if st.session_state.ctext.endswith("{FF}"):
                    st.session_state.ctext=st.session_state.ctext[:-4] # 移除最后4个字符
                st.rerun()

        # 显示文本转添加[ENTER]
        if "{03 00 " in st.session_state.ctext:
        # 脚本替换功能
            if btn_col1.button("脚本替换_NEW"):
                success, result = script_replace(record['jtext'], vtext)
                if success:
                    st.session_state.ctext = result
                    st.success("脚本替换成功！")
                    st.rerun()
                else:
                    st.error(result)

            if btn_col3.button("脚本替换"):
                success, result = script_replace_old(record['jtext'], vtext)
                if success:
                    st.session_state.ctext = result
                    st.success("脚本替换成功！")
                    st.rerun()
                else:
                    st.error(result)

        if btn_col2.button("🤖 AI 一键翻译"):
            import json
            with st.spinner("AI 正在翻译中，请稍候..."):
                jtext_clean = display_text(record['jtext'])
                # 发送给 AI 之前去掉前后的空白字符（尤其是全角空格），以免大模型处理或者返回不一致
                lines = [line.strip() for line in jtext_clean.split('\n') if line.strip()]
                
                if not lines:
                    st.warning("没有可翻译的文本。")
                else:
                    source_hash = hashlib.md5((table + str(record['ID']) + "".join(lines)).encode('utf-8')).hexdigest()
                    cached = get_cached_translation(source_hash)
                    
                    if cached:
                        translated_lines = json.loads(cached)
                        st.success("使用了缓存的翻译结果！")
                        success = True
                    else:
                        glossary = get_glossary(table)
                        success, translated_lines = call_dashscope_api(lines, glossary)
                        if success:
                            from ai_translation import get_ai_config
                            import json
                            model_used = get_ai_config('model_name')
                            set_cached_translation(source_hash, json.dumps(lines, ensure_ascii=False), json.dumps(translated_lines, ensure_ascii=False), model_used)
                    
                    if success:
                        vtext_new = '\n'.join(translated_lines)
                        st.session_state.temp_text = vtext_new
                        
                        # 自动执行脚本替换填回控制符
                        replace_success, final_result = script_replace(record['jtext'], vtext_new)
                        if replace_success:
                            st.session_state.ctext = final_result
                            st.success("AI 翻译并自动回填成功！请核对并保存。")
                            st.rerun()
                        else:
                            st.warning("AI 翻译成功，但自动回填失败，请在右侧检查临时翻译文本。")
                            st.rerun()
                    else:
                        # 检查是否是包含了部分结果的字典（来自翻译行数不匹配）
                        if isinstance(translated_lines, dict) and "partial_result" in translated_lines:
                            error_msg = translated_lines["error"]
                            partial_res = translated_lines["partial_result"]
                            st.error(f"翻译失败: {error_msg}")
                            
                            if isinstance(partial_res, list) and len(partial_res) > 0:
                                st.session_state.temp_text = '\n'.join(partial_res)
                                st.warning("已将不匹配的翻译结果放入右侧临时文本区，请手工调整后点击'脚本替换'。")
                                time.sleep(1.5)
                                st.rerun()
                        else:
                            st.error(f"翻译失败: {translated_lines}")

        if s_left.button("保存译文"):
            time.sleep(0.5)
            if validate_string(st.session_state.newctext):
                with st.spinner('正在保存...'):
                    success, message = update_record(table, ids[selected_id], st.session_state.newctext, st.session_state.username)
                    if success:
                        release_lock(table, ids[selected_id])  # 保存成功后释放锁定
                        st.success(message)
                        del st.session_state.ctext
                        if 'temp_text' in st.session_state:
                            del st.session_state.temp_text
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)
            else:
                st.error('输入文本存在控制符错误，请检查！')

        # 当用户切换到其他记录时释放锁定
        if 'previous_id' not in st.session_state:
            st.session_state.previous_id = selected_id
        elif st.session_state.previous_id != selected_id:
            release_lock(table, ids[st.session_state.previous_id])
            st.session_state.previous_id = selected_id

# 主程序
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'page' not in st.session_state:
        st.session_state.page = 'login'
    if 'selected_table' not in st.session_state:
        st.session_state.selected_table = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if not st.session_state.logged_in:
        if st.session_state.page == 'change_password':
            change_password_page()
        else:
            login_page()
    elif st.session_state.page == 'edit':
        st.set_page_config(layout="wide")
        edit_page()
    elif st.session_state.page == 'ai_settings':
        st.set_page_config(layout="centered")
        from ai_translation import render_ai_settings
        render_ai_settings()
        if st.button("返回"):
            st.session_state.page = 'select_table'
            st.rerun()
    elif st.session_state.page == 'user_admin':
        st.set_page_config(layout="centered")
        from user_admin import main as user_admin_page
        user_admin_page()
        if st.button("返回"):
            st.session_state.page = 'select_table'
            st.rerun()
    elif st.session_state.page == 'conflict_analysis':
        st.set_page_config(layout="wide")
        from conflict_analyzer import render_conflict_analyzer
        render_conflict_analyzer()
        if st.button("返回"):
            st.session_state.page = st.session_state.get('conflict_return_page', 'select_table')
            st.rerun()
    elif st.session_state.page == 'glossary_mgmt':
        st.set_page_config(layout="wide")
        from ai_translation import render_glossary_management
        render_glossary_management(st.session_state.get('selected_table', 'global'))
        if st.button("返回编辑界面"):
            st.session_state.page = 'edit'
            st.rerun()
    else:
        st.set_page_config(layout="centered")
        table_selection_page()
if __name__ == '__main__':
    main()
