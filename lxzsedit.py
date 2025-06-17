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
        with create_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT max(ID) as get_id FROM `{fname}` WHERE `{f_text}` LIKE %s AND ID < %s"
            cursor.execute(query, (f"%{s_text}%", s_id))
            result = cursor.fetchone()
            return result['get_id'] if result else None
    except Error as e:
        st.error("查找过程中出错。")
        return None
        if conn.is_connected():
            cursor.close()
            conn.close()
            
# 向后查找包含指定字符的数据ID
def get_id_down(fname, s_id, s_text, f_text):
    try:
        with create_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT min(ID) as get_id FROM `{fname}` WHERE `{f_text}` LIKE %s AND ID > %s"
            cursor.execute(query, (f"%{s_text}%", s_id))
            result = cursor.fetchone()
            return result['get_id'] if result else None
    except Error as e:
        st.error("查找过程中出错。")
        return None
        if conn.is_connected():
            cursor.close()
            conn.close()
            

# 读取数据表指定ID内容
def get_table_data(fname,id):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM `{fname}` where ID='{id}'")
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
                viewtext += ls
            elif ls.startswith("{D1 07"):  # 添加关键词
                viewtext += ls
            elif (ls in ["{CC 00 00 00 }", "{CC 00 01 00 }", "{04 00 }", "{69 00 }", "{75 00 }"]) or ls.startswith("{CC 00 ") :
                display_text += viewtext + "\n"
                viewtext = ""
                if ls == "{04 00 }":
                    display_text += viewtext + "\n"
            if ls.startswith("{87}"): #添加姓名编码
                viewtext += ls
        elif not ls.startswith("#"):  #去除注释行
            viewtext += ls

    if viewtext:
        display_text += viewtext + "\n"

    return display_text


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
# 获取更新信息
def get_update_info():
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT version, update_info FROM update_logs ORDER BY version DESC")
        updates = cursor.fetchall()
        
        # 合并所有更新信息
        update_text = ""
        for update in updates:
            update_text += f"Version {update['version']}:\n{update['update_info']}\n\n"
        return update_text
    except Error as e:
        st.error(f"Error: {e}")
        return "无法获取更新信息"
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def login_page():
    st.title("流行之神脚本编辑系统 1.6")
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
    st.text_area("更新日志", value=get_update_info(), height=200, disabled=True)

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
    selected_id = st.sidebar.slider("滑动滚动条选择记录", min_value=0, max_value=len(ids) - 1, value=st.session_state.nowid,key="selected_id")
    if st.session_state.nowid != selected_id:
        st.session_state.need_replace = False
        if 'ctext' in st.session_state:
            del st.session_state.ctext
    st.session_state.nowid=selected_id
    
   
    b_up,b_down,b_input_id,b_goto=st.sidebar.columns(4, gap="small")
    button_up=b_up.button("＜＜")
    button_down=b_down.button("＞＞")
    input_id=b_input_id.number_input("", min_value=0, max_value=len(ids) - 1, value="min",label_visibility="collapsed")
    button_goto=b_goto.button("转到")
    
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
    search_up=s_up.button("向前查找")
    search_down=s_down.button("向后查找")
    s_replace,s_rpbutton=st.sidebar.columns([0.70,0.30], gap="small")
    replace_text = s_replace.text_input("替换为",label_visibility="collapsed")
    do_replace=s_rpbutton.button("替换")
    Control_view=st.sidebar.checkbox("日文显示控制符", value=True)

    # 添加返回按钮
    if st.sidebar.button("返回选择界面"):
        st.session_state.page = 'select_table'
        del st.session_state.nowid
        del st.session_state.selected_table
        del st.session_state.ctext
        del st.session_state.previous_id
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
           
        if ('temp_text' in st.session_state): #如果存在输入的译文
            vtext = s_right.text_area("临时翻译文本", value=st.session_state.temp_text, height=500)
        else:
            vtext = s_right.text_area("模拟显示（也可用于存放临时翻译文本）", value=display_text(st.session_state.ctext), height=500)

        # 显示文本转译文
        if "{FF}" in st.session_state.ctext:
            if s_right.button("文本转换"):
                st.session_state.ctext=vtext.replace("\n","{FF}")
                if st.session_state.ctext.endswith("{FF}"):
                    st.session_state.ctext=st.session_state.ctext[:-4] # 移除最后4个字符
                st.rerun()

        # 显示文本转添加[ENTER]
        if "[ENTER]" in st.session_state.ctext:
        # 脚本替换功能
            if s_right.button("脚本替换"):
                success, result = script_replace(record['jtext'], vtext)
                if success:
                    st.session_state.ctext = result
                    st.success("脚本替换成功！")
                    st.rerun()
                else:
                    st.error(result)

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
    else:
        st.set_page_config(layout="centered")
        table_selection_page()
if __name__ == '__main__':
    main()
