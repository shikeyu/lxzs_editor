import streamlit as st
import mysql.connector
from mysql.connector import Error
import bcrypt

# 连接到远端 MySQL 数据库
def create_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )

# 加密密码
def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    return hashed

# 添加新用户或更新现有用户密码
def add_or_update_user(username, password):
    hashed_password = hash_password(password)
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # 检查用户是否已存在
        cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            # 更新现有用户的密码
            cursor.execute("UPDATE Users SET password = %s WHERE username = %s", (hashed_password, username))
            message = "用户密码已更新成功！"
        else:
            # 添加新用户
            cursor.execute("INSERT INTO Users (username, password) VALUES (%s, %s)", (username, hashed_password))
            message = "新用户添加成功！"
        
        conn.commit()
        st.success(message)
    except Error as e:
        st.error(f"错误：{e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 删除用户
def delete_user(username):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Users WHERE username = %s", (username,))
        conn.commit()
        if cursor.rowcount > 0:
            st.success("User deleted successfully!")
        else:
            st.warning("User not found!")
    except Error as e:
        st.error(f"Error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 获取所有用户
def get_all_users():
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT Userid, Username FROM Users")
        users = cursor.fetchall()
        return users
    except Error as e:
        st.error(f"错误：{e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 获取所有表格
def get_all_tables():
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT ID, title FROM tablelist")
        tables = cursor.fetchall()
        return tables
    except Error as e:
        st.error(f"错误：{e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 更新用户权限
def update_user_permissions(user_id, table_ids):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # 先删除该用户的所有现有权限
        cursor.execute("DELETE FROM user_table WHERE user_id = %s", (user_id,))
        
        # 添加新的权限
        for table_id in table_ids:
            cursor.execute("INSERT INTO user_table (user_id, table_id) VALUES (%s, %s)", (user_id, table_id))
        
        conn.commit()
        st.success("用户权限更新成功！")
    except Error as e:
        st.error(f"错误：{e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 获取用户权限
def get_user_permissions(user_id):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT table_id FROM user_table WHERE user_id = %s", (user_id,))
        permissions = [row[0] for row in cursor.fetchall()]
        return permissions
    except Error as e:
        st.error(f"错误：{e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# Streamlit 用户界面
def main():
    st.title("用户管理")

    # 添加或更新用户
    st.header("添加或更新用户")
    new_username = st.text_input("请输入用户名")
    new_password = st.text_input("请输入密码", type="password")

    if st.button("添加/更新"):
        if new_username and new_password:
            add_or_update_user(new_username, new_password)
        else:
            st.warning("用户名和密码必须同时输入！")

    st.write("---")

    # 删除用户
    st.header("删除用户")
    del_username = st.text_input("要删除的用户名")

    if st.button("删除"):
        if del_username:
            delete_user(del_username)
        else:
            st.warning("请输入要删除的用户名！")

    st.write("---")

    # 用户权限管理
    st.header("用户权限管理")
    
    users = get_all_users()
    tables = get_all_tables()
    
    selected_user = st.selectbox("选择用户", options=[user['Username'] for user in users])
    selected_user_id = next(user['Userid'] for user in users if user['Username'] == selected_user)
    
    # 获取用户当前的权限
    current_permissions = get_user_permissions(selected_user_id)
    
    st.write("选择表格权限：")
    selected_table_ids = []
    for table in tables:
        is_checked = st.checkbox(table['title'], value=table['ID'] in current_permissions)
        if is_checked:
            selected_table_ids.append(table['ID'])
    
    if st.button("更新权限"):
        update_user_permissions(selected_user_id, selected_table_ids)

if __name__ == '__main__':
    main()
