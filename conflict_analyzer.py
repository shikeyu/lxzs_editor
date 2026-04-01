import re
import pandas as pd
import streamlit as st

def extract_visible_text(text):
    """
    提取文本中的可见部分，去除所有控制符，除了特定的人名占位符等，
    或者直接将所有 {...} 控制符去掉，以获得纯净的对话文本进行对比。
    """
    if not text:
        return ""
    # 这里我们只保留非控制符的文本内容，或者对特殊控制符进行替换
    # 按照 lxzsedit.py 的 display_text 逻辑进行简化
    text = text.replace("\r\n", "\n")
    tokens = re.split(r'(\{[^\{\}]+\})', text)
    visible_text = ""
    for i, token in enumerate(tokens):
        if i % 2 == 1: # 控制符
            if token.startswith("{79"):
                visible_text += token[19:-1]
            elif token.startswith("{23"):
                visible_text += token[10:-1]
            elif token.startswith("{D9"):
                visible_text += "＃"
            elif token == "{D5 00 08 00 }":
                visible_text += "风海"
            elif token == "{D5 00 09 00 }":
                visible_text += "纯也"
            elif token.startswith("{D5 00 "):
                visible_text += "{D5}"
            elif token.startswith("{D1 07"):
                visible_text += "{D1}"
            elif token.startswith("{CD "):
                visible_text += "{CD}"
            elif token.startswith("{CE "):
                visible_text += "{CE}"
            elif token.startswith("{87}"):
                visible_text += token
        else: # 纯文本
            # 去除注释
            lines = token.split("\n")
            for line in lines:
                if not line.startswith("#"):
                    visible_text += line
                    
    # 去除前后空白
    return visible_text.strip()

def parse_dialogue_groups(jtext, ctext):
    """
    解析原始文本和译文，识别由 {03 00 ...} 和 {04 00 ...} 开头的控制符分组的对话数据。
    """
    # 以控制符为界分割
    j_tokens = re.split(r'(\{[^\{\}]+\})', jtext) if jtext else []
    c_tokens = re.split(r'(\{[^\{\}]+\})', ctext) if ctext else []
    
    def group_tokens(tokens):
        groups = []
        current_group = []
        for i, token in enumerate(tokens):
            if i % 2 == 1: # 控制符
                if token.startswith("{03 00 ") or token.startswith("{04 00 "):
                    if current_group:
                        groups.append(current_group)
                    current_group = [token]
                else:
                    current_group.append(token)
            else:
                current_group.append(token)
        if current_group:
            groups.append(current_group)
        return groups

    j_groups = group_tokens(j_tokens)
    c_groups = group_tokens(c_tokens)
    
    results = []
    # 尽可能一一对应
    for i in range(max(len(j_groups), len(c_groups))):
        j_group_text = "".join(j_groups[i]) if i < len(j_groups) else ""
        c_group_text = "".join(c_groups[i]) if i < len(c_groups) else ""
        
        j_visible = extract_visible_text(j_group_text)
        c_visible = extract_visible_text(c_group_text)
        
        # 只保留有可见文本的组
        if j_visible or c_visible:
            results.append((j_visible, c_visible))
            
    return results

def detect_conflicts(data_rows):
    """
    检测同一原文对应不同译文的情况。
    data_rows: 列表，每个元素为字典 {'table': table_name, 'id': id, 'jtext': jtext, 'ctext': ctext}
    """
    # mapping: { original_text: { translated_text: [(table, id, group_idx), ...] } }
    mapping = {}
    
    for row in data_rows:
        table_name = row.get('table', 'Unknown')
        record_id = row.get('id', 'Unknown')
        jtext = row.get('jtext', '')
        ctext = row.get('ctext', '')
        
        groups = parse_dialogue_groups(jtext, ctext)
        
        for idx, (orig, trans) in enumerate(groups):
            if not orig:
                continue
                
            if orig not in mapping:
                mapping[orig] = {}
                
            if trans not in mapping[orig]:
                mapping[orig][trans] = []
                
            mapping[orig][trans].append({
                'table': table_name,
                'id': record_id,
                'group_idx': idx
            })
            
    # 筛选出存在冲突的（同一原文有多个不同的译文，忽略空译文导致的冲突或提供选项）
    conflicts = []
    for orig, trans_map in mapping.items():
        # 如果有超过1个不同的译文，说明有冲突
        # 可以选择忽略空的译文（即未翻译的情况）
        valid_translations = [t for t in trans_map.keys() if t.strip()]
        if len(valid_translations) > 1:
            conflicts.append({
                'original': orig,
                'translations': trans_map
            })
            
    return conflicts

def render_conflict_analyzer():
    st.title("🔍 本表脚本对话冲突检测")
    
    # 获取数据库连接
    import lxzsedit
    
    # 从 session_state 获取当前要检测的表
    target_tables = st.session_state.get('conflict_default_tables', [])
    if not target_tables:
        st.warning("未指定需要检测的数据表，请从编辑页面进入。")
        return
        
    t_name = target_tables[0]
    
    # 获取表名别名
    table_title = t_name
    try:
        tables = lxzsedit.get_filelist()
        for t in tables:
            if t['table_name'] == t_name:
                table_title = t['title']
                break
    except Exception:
        pass
        
    st.markdown(f"检测数据表 **{table_title} ({t_name})** 中，同一句日文原文对应多个不同中文译文的冲突情况。")
    
    if st.button("开始检测"):
        with st.spinner(f"正在扫描数据表 {table_title}..."):
            all_data = []
            
            try:
                conn = lxzsedit.create_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(f"SELECT ID, jtext, ctext FROM `{t_name}`")
                rows = cursor.fetchall()
                for row in rows:
                    all_data.append({
                        'table': t_name,
                        'id': row['ID'],
                        'jtext': row['jtext'],
                        'ctext': row['ctext']
                    })
            except Exception as e:
                st.error(f"读取表 {t_name} 时出错: {e}")
                return
            finally:
                if 'conn' in locals() and conn.is_connected():
                    cursor.close()
                    conn.close()
            
            st.info(f"共加载 {len(all_data)} 条记录，正在分析对话...")
            
            conflicts = detect_conflicts(all_data)
            
            if not conflicts:
                st.success("🎉 太棒了！没有发现任何翻译冲突。")
            else:
                st.warning(f"⚠️ 发现了 {len(conflicts)} 处原文对应多个不同译文的冲突！")
                
                # 准备导出数据
                export_data = []
                for idx, conflict in enumerate(conflicts, 1):
                    orig = conflict['original']
                    for trans, locations in conflict['translations'].items():
                        for loc in locations:
                            export_data.append({
                                "冲突组号": idx,
                                "原文": orig,
                                "译文": trans,
                                "所在表": loc['table'],
                                "表别名": table_title,
                                "记录ID": loc['id'],
                                "对话序号": loc['group_idx'] + 1
                            })
                            
                df = pd.DataFrame(export_data)
                
                # 下载按钮
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 导出冲突报告 (CSV)",
                    data=csv,
                    file_name=f'translation_conflicts_{t_name}.csv',
                    mime='text/csv',
                )
                
                # 页面展示
                st.markdown("### 冲突详情列表")
                for idx, conflict in enumerate(conflicts, 1):
                    with st.expander(f"冲突 #{idx}: {conflict['original'][:50]}..."):
                        st.markdown("**原文:**")
                        st.code(conflict['original'], language="text")
                        
                        st.markdown("**不同译文及出现位置:**")
                        for trans, locations in conflict['translations'].items():
                            st.markdown(f"- **译文**: `{trans if trans else '(空)'}`")
                            loc_strs = [f"ID: `{loc['id']}`" for loc in locations]
                            st.caption(f"  位置: {', '.join(loc_strs)}")
