import streamlit as st
from streamlit.components.v1 import html
from openai import OpenAI, OpenAIError
import os
import glob
import json
import re

# --- CÁC HÀM TIỆN ÍCH ---
def rfile(name_file):
    """Đọc nội dung từ một file và trả về dưới dạng chuỗi."""
    try:
        with open(name_file, "r", encoding="utf-8") as file:
            return file.read().strip()
    except Exception:
        return ""

def load_config_data(config_file, default_data):
    """Tải dữ liệu cấu hình từ file, nếu lỗi thì dùng dữ liệu mặc định."""
    try:
        with open(config_file, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip() and not line.startswith('#')]
            while len(lines) < len(default_data):
                lines.append(default_data[len(lines)])
            return lines[:len(default_data)]
    except Exception:
        return default_data

# --- CÁC HÀM XỬ LÝ DỮ LIỆU ---

@st.cache_data(ttl=600)
def get_all_products_as_dicts(folder_path="product_data"):
    """
    Tải tất cả sản phẩm, chuyển đổi thành danh sách các dictionary.
    Code sẽ tự động cố gắng chuyển các giá trị có dạng số thành kiểu số để so sánh.
    """
    product_index = []
    if not os.path.isdir(folder_path):
        return []
    
    file_paths = [f for f in glob.glob(os.path.join(folder_path, '*.txt')) if not os.path.basename(f) == '_link.txt']
    
    for file_path in file_paths:
        content = rfile(file_path)
        if not content: continue
            
        product_dict = {}
        for line in content.split('\n'):
            if ':' in line:
                key, value_str = line.split(':', 1)
                key_clean = key.strip().lower().replace(" ", "_") # Chuẩn hóa key
                value_clean = value_str.strip()
                
                try:
                    numerical_part = re.sub(r'[^\d.]', '', value_clean)
                    if numerical_part:
                        product_dict[key_clean] = float(numerical_part)
                    else:
                        product_dict[key_clean] = value_clean
                except (ValueError, TypeError):
                    product_dict[key_clean] = value_clean
        
        product_dict['original_content'] = content
        if product_dict:
            product_index.append(product_dict)
    return product_index

# --- CÁC CÔNG CỤ CHUYÊN DỤNG CHO AI (LOGIC BẰNG PYTHON) ---

def find_products(product_type: str = None, sort_key: str = None, sort_order: str = 'desc', n_results: int = 1):
    """
    Tìm kiếm, lọc và sắp xếp sản phẩm để trả lời các câu hỏi như 'căn hộ rẻ nhất', '3 biệt thự rộng nhất'.
    Công cụ này xử lý logic so sánh một cách chính xác bằng code Python.
    """
    all_products = get_all_products_as_dicts()
    products_to_process = all_products
    
    if product_type:
        products_to_process = [p for p in all_products if p.get("loai_san_pham", "").lower() == product_type.lower()]

    if not products_to_process:
        return "Không tìm thấy sản phẩm nào thuộc loại này."

    if sort_key:
        valid_products = [p for p in products_to_process if isinstance(p.get(sort_key), (int, float))]
        if not valid_products:
            return f"Không có dữ liệu hợp lệ để sắp xếp theo '{sort_key}'."
            
        is_descending = sort_order == 'desc'
        sorted_products = sorted(valid_products, key=lambda x: x[sort_key], reverse=is_descending)
        
        if n_results == 1 and len(sorted_products) > 0:
            top_value = sorted_products[0][sort_key]
            top_products = [p for p in sorted_products if p.get(sort_key) == top_value]
            return [p.get('original_content', '') for p in top_products]

        return [p.get('original_content', '') for p in sorted_products[:n_results]]

    return [p.get('original_content', '') for p in products_to_process[:n_results]]

def count_products_by_type(product_type: str = None):
    """Đếm chính xác số lượng sản phẩm."""
    all_products = get_all_products_as_dicts()
    if not product_type:
        return {"tong_so_luong": len(all_products)}
    count = sum(1 for p in all_products if p.get("loai_san_pham", "").lower() == product_type.lower())
    return {f"so_luong_{product_type.lower()}": count}

# --- LOGIC CHATBOT ---
def show_chatbot():
    openai_api_key = st.secrets.get("OPENAI_API_KEY")
    if not openai_api_key: st.error("Chưa có OpenAI API Key. Vui lòng thiết lập trong Streamlit Secrets."); return
    try:
        client = OpenAI(api_key=openai_api_key)
    except OpenAIError as e:
        st.error(f"Lỗi xác thực OpenAI API Key: {e}."); return

    tools = [
        {"type": "function", "function": {"name": "find_products", "description": "Tìm kiếm, lọc và sắp xếp sản phẩm. Dùng cho các câu hỏi như 'căn hộ rẻ nhất', 'biệt thự rộng nhất', 'top 3 giá cao nhất'.", "parameters": {"type": "object", "properties": {"product_type": {"type": "string", "description": "Loại sản phẩm cần tìm, ví dụ: 'căn hộ', 'biệt thự'."},"sort_key": {"type": "string", "description": "Thuộc tính để sắp xếp. Ví dụ: 'gia_thue' cho giá, 'dien_tich' cho diện tích."}, "sort_order": {"type": "string", "enum": ["asc", "desc"], "description": "'asc' cho tăng dần (rẻ nhất, hẹp nhất), 'desc' cho giảm dần (đắt nhất, rộng nhất)."}, "n_results": {"type": "integer", "description": "Số lượng kết quả trả về."}}}}},
        {"type": "function", "function": {"name": "count_products_by_type", "description": "Đếm chính xác tổng số sản phẩm hoặc số sản phẩm theo loại.", "parameters": {"type": "object", "properties": {"product_type": {"type": "string", "description": "Loại sản phẩm cần đếm. Để trống để đếm tất cả."}}}}}
    ]

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": rfile("02.assistant.txt") or "Tôi có thể giúp gì cho bạn?"}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])

    if prompt := st.chat_input("Bạn nhập nội dung cần trao đổi ở đây nhé?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        system_prompt = rfile("01.system_trainning.txt")
        # Luôn gửi lịch sử chat để AI nhớ ngữ cảnh
        messages_to_send = [{"role": "system", "content": system_prompt}] + st.session_state.messages

        with st.chat_message("assistant"):
            with st.spinner("Trợ lý đang suy nghĩ..."):
                try:
                    # BƯỚC 1: GỬI PROMPT VÀ CÔNG CỤ CHO AI
                    response = client.chat.completions.create(
                        model=rfile("module_chatgpt.txt").strip() or "gpt-4-turbo",
                        messages=messages_to_send, tools=tools, tool_choice="auto"
                    )
                    response_message = response.choices[0].message
                    tool_calls = response_message.tool_calls

                    # BƯỚC 2: KIỂM TRA XEM AI CÓ YÊU CẦU CHẠY CÔNG CỤ KHÔNG
                    if tool_calls:
                        available_functions = {"find_products": find_products, "count_products_by_type": count_products_by_type}
                        messages_to_send.append(response_message)
                        
                        # BƯỚC 3: THỰC THI CÔNG CỤ BẰNG CODE PYTHON
                        for tool_call in tool_calls:
                            function_name = tool_call.function.name
                            function_args = json.loads(tool_call.function.arguments)
                            function_to_call = available_functions[function_name]
                            function_response = function_to_call(**function_args)
                            messages_to_send.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": json.dumps(function_response, ensure_ascii=False)})
                        
                        # BƯỚC 4: GỬI KẾT QUẢ CỦA CÔNG CỤ NGƯỢC LẠI CHO AI ĐỂ TỔNG HỢP CÂU TRẢ LỜI
                        second_response = client.chat.completions.create(model=rfile("module_chatgpt.txt").strip() or "gpt-4-turbo", messages=messages_to_send, stream=True)
                        final_response = st.write_stream(second_response)
                        st.session_state.messages.append({"role": "assistant", "content": final_response})
                    else:
                        # Nếu AI không cần công cụ, chỉ hiển thị câu trả lời
                        st.markdown(response_message.content)
                        st.session_state.messages.append({"role": "assistant", "content": response_message.content})
                except OpenAIError as e:
                    st.error(f"Đã xảy ra lỗi với OpenAI: {e}")

# --- CÁC HÀM GIAO DIỆN ---
def show_main_page():
    st.subheader("✨ Các bài viết nổi bật")
    default_images = ["article_images/pic1.jpg", "article_images/pic2.jpg", "article_images/pic3.jpg"]
    default_titles = ["Tiêu đề bài viết 1", "Tiêu đề bài viết 2", "Tiêu đề bài viết 3"]
    image_paths = [path if os.path.exists(path) else f"https://placehold.co/400x267/a3e635/44403c?text=Thiếu+ảnh+{i+1}" for i, path in enumerate(default_images)]
    article_titles = load_config_data("config_titles.txt", default_titles)
    col1, col2, col3 = st.columns(3, gap="medium")
    for i, col in enumerate([col1, col2, col3]):
        with col:
            st.image(image_paths[i], use_container_width=True)
            if st.button(article_titles[i], use_container_width=True, key=f"btn{i+1}"):
                st.session_state.view = f"article_{i+1}"
                st.rerun()
    st.divider()
    if os.path.exists("logo.png"): st.image("logo.png")
    st.markdown(f"<h2 style='text-align: center;'>{rfile('00.xinchao.txt') or 'Chào mừng đến với Trợ lý AI'}</h2>", unsafe_allow_html=True)
    show_chatbot()

def show_article_page(article_number):
    if st.button("⬅️ Quay về Trang chủ"): st.session_state.view = "main"; st.rerun()
    st.divider()
    try:
        with open(f"03bai_viet/bai_viet_0{article_number}.html", "r", encoding="utf-8") as f:
            html(f.read(), height=800, scrolling=True)
    except FileNotFoundError:
        st.error(f"Lỗi: Không tìm thấy file bài viết số {article_number}.")

def main():
    st.set_page_config(page_title="Trợ lý AI", page_icon="🤖", layout="centered")
    st.markdown("""<style>
        [data-testid="stToolbar"], header, #MainMenu {visibility: hidden !important;}
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stChatMessageContent-user"]) { justify-content: flex-end; }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageContent-user"]) { flex-direction: row-reverse; }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage { height: 150px; width: 100%; overflow: hidden; border-radius: 0.5rem; }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage img { height: 100%; width: 100%; object-fit: cover; }
    </style>""", unsafe_allow_html=True) 
    
    if "view" not in st.session_state: 
        st.session_state.view = "main"
        
    view_map = {
        "main": show_main_page, 
        "article_1": lambda: show_article_page(1), 
        "article_2": lambda: show_article_page(2), 
        "article_3": lambda: show_article_page(3)
    }
    view_map.get(st.session_state.view, show_main_page)()

if __name__ == "__main__":
    main()