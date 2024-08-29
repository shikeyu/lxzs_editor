import streamlit as st
import mysql.connector
import bcrypt
from mysql.connector import Error
from datetime import datetime

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
        cursor.execute(f"SELECT max(ID) as get_id FROM `{fname}` WHERE `{f_text}` LIKE '%{s_text}%' AND ID < {s_id}")
        result = cursor.fetchall()
        return result[0]['get_id']
    except Error as e:
        st.error(f"Error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            
# 向后查找包含指定字符的数据ID
def get_id_down(fname,s_id,s_text,f_text):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT min(ID) as get_id FROM `{fname}` WHERE `{f_text}` LIKE '%{s_text}%' AND ID > {s_id}")
        result = cursor.fetchall()
        return result[0]['get_id']
    except Error as e:
        st.error(f"Error: {e}")
        return []
    finally:
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
    try:
        conn = create_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f"UPDATE `{fname}` SET ctext = %s, editor = %s, update_time = %s WHERE id = %s", (ctext, editor, now, record_id))
        conn.commit()
        st.success("Record updated successfully!")
    except Error as e:
        st.error(f"Error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

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

# 表选择界面
def table_selection_page():
    st.title("请选择要修改的文本库")
    tblist = get_filelist()

    #生成简介列表及表映射
    table_mapping = {row['title']: row for row in tblist}
    titles = [row['title'] for row in tblist]

    selected_table = st.selectbox("文本库", titles)
    if st.button("打开数据表"):
        if selected_table:
            st.session_state.selected_table =table_mapping[selected_table]['table_name']
            st.session_state.selected_tabletitle=selected_table
            st.session_state.page = 'edit'
            st.session_state.nowid=-1
            st.rerun()
        else:
            st.warning("请选择要打开的表")

# 编辑界面
def edit_page():
    table = st.session_state.selected_table
    table_title=st.session_state.selected_tabletitle
    st.title(f"当前数据为: {table_title}")
    data_id = get_table_id(table)
    if not data_id:
        st.warning("No data found in the selected table.")
        return

    # 生成 ID 列表
    ids = [row['ID'] for row in data_id]

    if st.session_state.nowid<0:
        st.session_state.nowid=0

    # 通过滑动条选择记录行
    selected_id = st.sidebar.slider("滑动滚动条选择记录", min_value=0, max_value=len(ids), value=st.session_state.nowid)
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
    data = get_table_data(table,ids[selected_id])
    id_mapping = {row['ID']: row for row in data}
    if not data:
        st.warning("No data found in the selected table.")
        return
    record = data[0]

    if record:
        st.write("编号:",hex(record['ID']),"   编辑者:",record['editor'],"   更新时间:",record['update_time'])
        st.text_area("日文", value=record['jtext'], height=200)

        # 编辑 ctext 字段
        ctext = st.text_area("译文", value=record['ctext'], height=250)

        if st.button("保存译文"):
            if st.session_state.username != 'guest':
                update_record(table, ids[selected_id], ctext, st.session_state.username)
            else:
                st.info('演示用户无法更新数据！')

    search_text = st.sidebar.text_input("查找译文")
    search_in=st.sidebar.radio("搜索范围",["原文","译文"],index=1,horizontal=1)
    s_up,s_down=st.sidebar.columns(2, gap="small")
    search_up=s_up.button("向前查找")
    search_down=s_down.button("向后查找")
    #向前查找字符串
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
        edit_page()
    else:
        table_selection_page()
if __name__ == '__main__':
    main()
