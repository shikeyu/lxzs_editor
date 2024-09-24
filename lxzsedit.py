import streamlit as st
import mysql.connector
import bcrypt
from mysql.connector import Error
from datetime import datetime
import time

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

    allyw = yw1.split("\n")
    for ls in allyw:
        if ls.startswith("{"):
            if ls.startswith("{79"):  # 添加选择项
                display_text += ls[19:] + "\n"
            elif ls.startswith("{23"):  # 添加未知项
              display_text += ls[10:-1] + "\n"
            elif ls.startswith("{D9"):  # 添加未知项
                viewtext += "＃"
            elif ls == "{D5 00 08 00 }":
                viewtext += "风海"
            elif ls == "{D5 00 09 00 }":  # 添加姓名
                viewtext += "纯也"
            elif ls.startswith("{D1 07"):  # 添加关键词
                viewtext += ls
            elif ls in ["{CC 00 00 00 }", "{CC 00 01 00 }", "{04 00 }", "{69 00 }"]:
                display_text += viewtext + "\n"
                viewtext = ""
                if ls == "{04 00 }":
                    display_text += viewtext + "\n"
        else:
            viewtext += ls

    if viewtext:
        display_text += viewtext + "\n"

    return display_text


# 登录界面
def login_page():
    st.title("流行之神脚本编辑系统")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
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
        st.session_state.nowid=0

    # 通过滑动条选择记录行
    selected_id = st.sidebar.slider("滑动滚动条选择记录", min_value=0, max_value=len(ids), value=st.session_state.nowid,key="selected_id")
    st.session_state.nowid=selected_id
   
    b_up,b_down=st.sidebar.columns(2, gap="small")
    button_up=b_up.button("上一条")
    button_down=b_down.button("下一条")
    #row1=st.row([button_up,button_down])
    if button_up:
        if st.session_state.nowid>=0:
            st.session_state.nowid -=1
            st.rerun()
    if button_down:
        if st.session_state.nowid<len(ids):
            st.session_state.nowid +=1
            st.rerun()
            
    # 查找功能按钮
    search_text = st.sidebar.text_input("查找译文")
    search_in=st.sidebar.radio("搜索范围",["原文","译文"],index=1,horizontal=1)
    s_up,s_down=st.sidebar.columns(2, gap="small")
    search_up=s_up.button("向前查找")
    search_down=s_down.button("向后查找")
    Control_view=st.sidebar.checkbox("日文显示控制符", value=True)
    # 向前查找字符串
    if search_up:
        if search_in=='原文':
            found_id=get_id_up(table,ids[selected_id],search_text,'jtext')
        else:
            found_id=get_id_up(table,ids[selected_id],search_text,'ctext')
        if found_id:
            st.session_state.nowid=ids.index(found_id)
            st.rerun()
        
    #向后查找字符串
    if search_down:
        if search_in=='原文':
            found_id=get_id_down(table,ids[selected_id],search_text,'jtext')
        else:
            found_id=get_id_down(table,ids[selected_id],search_text,'ctext')
        if found_id:
            st.session_state.nowid=ids.index(found_id)
            st.rerun()

    data = get_table_data(table, ids[selected_id])
    if not data:
        st.warning("No data found in the selected table.")
        return
    record = data[0]

    if record:
        st.write("编号:", hex(record['ID']), "   编辑者:", record['editor'], "   更新时间:", record['update_time'])
        # 左右分两列
        s_left, s_right = st.columns(2, gap="small")
        
        if Control_view:
            s_left.text_area("日文", value=record['jtext'], height=200)
        else:
            s_left.text_area("日文", value=display_text(record['jtext']), height=200)  

        ctext=record['ctext']

        # 编辑 ctext 字段
        ctext = s_left.text_area("译文", value=record['ctext'], height=250, key="ctext")
           
        vtext = s_right.text_area("模拟显示", value=display_text(ctext), height=500)


        if s_left.button("保存译文"):
            time.sleep(0.5)
            if validate_string(ctext):
                with st.spinner('正在保存...'):
                    success, message = update_record(table, ids[selected_id], ctext, st.session_state.username)
                    if success:
                        st.success(message)
                        time.sleep(0.5)  # 给一点时间让数据库更新
                        st.rerun()
                    else:
                        st.error(message)
            else:
                st.error('输入文本存在控制符错误，请检查！')


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
        login_page()
    elif st.session_state.page == 'edit':
        st.set_page_config(layout="wide")
        edit_page()
    else:
        table_selection_page()
if __name__ == '__main__':
    main()
