import streamlit as st
from streamlit.components.v1 import html
import google.generativeai as genai
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
                key_clean = key.strip()
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
    Tìm kiếm, lọc và sắp xếp sản phẩm. Luôn trả về một dictionary chứa một chuỗi kết quả duy nhất.
    """
    all_products = get_all_products_as_dicts()

    products_to_process = all_products
    if product_type:
        products_to_process = [p for p in all_products if p.get("loai_san_pham", "").lower() == product_type.lower()]

    if not products_to_process:
        return {"result": "Không tìm thấy sản phẩm nào thuộc loại này."}

    if sort_key:
        valid_products = [p for p in products_to_process if isinstance(p.get(sort_key), (int, float))]
        if not valid_products:
            return {"result": f"Không có dữ liệu hợp lệ để sắp xếp theo '{sort_key}'."}
            
        is_descending = sort_order == 'desc'
        sorted_products = sorted(valid_products, key=lambda x: x[sort_key], reverse=is_descending)
        
        products_to_return = sorted_products
        if n_results == 1 and len(sorted_products) > 0:
            top_value = sorted_products[0][sort_key]
            products_to_return = [p for p in sorted_products if p.get(sort_key) == top_value]
        
        final_content_list = [p.get('original_content', '') for p in products_to_return[:n_results]]
    
    else:
        final_content_list = [p.get('original_content', '') for p in products_to_process[:n_results]]

    # Nối tất cả kết quả thành một chuỗi văn bản duy nhất
    response_string = "\n\n---\n\n".join(final_content_list)
    return {"result": f"Tìm thấy {len(final_content_list)} sản phẩm:\n{response_string}"}


def count_products_by_type(product_type: str = None):
    """Đếm chính xác số lượng sản phẩm và trả về một chuỗi."""
    all_products = get_all_products_as_dicts()
    if not product_type:
        total_count = len(all_products)
        return {"result": f"Tổng số sản phẩm là {total_count}."}
        
    count = sum(1 for p in all_products if p.get("loai_san_pham", "").lower() == product_type.lower())
    return {"result": f"Số lượng sản phẩm loại '{product_type}' là {count}."}

# --- LOGIC CHATBOT VỚI GEMINI ---
def show_chatbot():
    google_api_key = st.secrets.get("GOOGLE_API_KEY")
    if not google_api_key:
        st.error("Chưa có Google API Key. Vui lòng thêm vào secrets.toml")
        return
    try:
        genai.configure(api_key=google_api_key)
    except Exception as e:
        st.error(f"Lỗi cấu hình Gemini: {e}")
        return

    tools = [find_products, count_products_by_type]
    model_name = rfile("module_gemini.txt").strip() or "gemini-1.5-pro"
    
    if "gemini_model" not in st.session_state:
        st.session_state.gemini_model = genai.GenerativeModel(model_name=model_name, tools=tools)
    if "chat_session" not in st.session_state:
        st.session_state.chat_session = st.session_state.gemini_model.start_chat()
    if "messages" not in st.session_state:
        initial_message = rfile("02.assistant.txt") or "Tôi có thể giúp gì cho bạn?"
        st.session_state.messages = [{"role": "assistant", "content": initial_message}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Bạn nhập nội dung cần trao đổi ở đây nhé?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        user_prompt = st.session_state.messages[-1]["content"]
        
        full_prompt = (rfile("01.system_trainning.txt") + "\n\nHỏi: " + user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Trợ lý đang suy nghĩ..."):
                try:
                    response = st.session_state.chat_session.send_message(full_prompt)

                    if response.parts and response.parts[0].function_call:
                        function_call = response.parts[0].function_call
                        function_name = function_call.name
                        
                        available_functions = {
                            "find_products": find_products,
                            "count_products_by_type": count_products_by_type,
                        }
                        
                        function_to_call = available_functions[function_name]
                        function_args = {key: value for key, value in function_call.args.items()}
                        
                        function_response_data = function_to_call(**function_args)

                        # Gửi trực tiếp dictionary trả về từ hàm, để thư viện tự xử lý
                        response = st.session_state.chat_session.send_message(
                            genai.Part(function_response=genai.protos.FunctionResponse(
                                name=function_name,
                                response=function_response_data,
                            ))
                        )
                    
                    final_response = response.text
                    st.markdown(final_response)
                    st.session_state.messages.append({"role": "assistant", "content": final_response})

                except Exception as e:
                    st.error(f"Đã xảy ra lỗi với Gemini: {e}")

# --- CÁC HÀM CÒN LẠI ---
def check_login():
    """Kiểm tra mật khẩu từ file password.txt."""
    if st.session_state.get("authenticated", False):
        return True
    
    st.title("🔐 Đăng nhập vào ứng dụng")
    
    correct_password = rfile("password.txt")
    if not correct_password:
        st.error("Lỗi: Không tìm thấy tệp 'password.txt' hoặc tệp trống.")
        return False

    with st.form("login_form"):
        password = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            if password == correct_password:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Mật khẩu không chính xác.")
    return False

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
    if not check_login(): return
    with st.sidebar:
        st.success("✅ Đã đăng nhập")
        if st.button("Đăng xuất"):
            for key in ["authenticated", "messages", "view", "chat_session", "gemini_model"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
    if "view" not in st.session_state: st.session_state.view = "main"
    view_map = {"main": show_main_page, "article_1": lambda: show_article_page(1), "article_2": lambda: show_article_page(2), "article_3": lambda: show_article_page(3)}
    view_map.get(st.session_state.view, show_main_page)()

if __name__ == "__main__":
    main()
