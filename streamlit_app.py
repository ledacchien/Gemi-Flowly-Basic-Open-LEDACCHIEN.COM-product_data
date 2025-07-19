import streamlit as st
from streamlit.components.v1 import html
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from streamlit.errors import StreamlitAPIException, StreamlitSecretNotFoundError
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

# --- CÁC HÀM XỬ LÝ DỮ LIỆU SẢN PHẨM ---
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
                    # Cố gắng chuyển đổi các chuỗi có số thành kiểu số
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

# --- HÀM CHÀO HỎI ĐỘNG DỰA TRÊN SẢN PHẨM ---
def make_greeting_message(product_dicts):
    if not product_dicts:
        return "Chào bạn, mình là Flowly – trợ lý AI của ledacchien.com! Hiện tại chưa có dịch vụ hoặc khóa học nào đang mở. Vui lòng quay lại sau hoặc liên hệ Zalo để được hỗ trợ."
    lines = ["Chào bạn, mình là Flowly – trợ lý AI của ledacchien.com! Dưới đây là các dịch vụ/khoá học hiện có:"]
    for idx, p in enumerate(product_dicts, 1):
        # Ưu tiên lấy tên sản phẩm từ các trường chuẩn hóa, nếu không thì lấy dòng đầu tiên trong file
        name = p.get('ten_san_pham') or p.get('tên_sản_phẩm') or p.get('ten') or p.get('tên') \
               or p.get('original_content', '').split('\n')[0]
        lines.append(f"{idx}. {name}")
    lines.append("Bạn quan tâm đến dịch vụ nào, hoặc muốn so sánh thêm không?")
    return "\n".join(lines)

# --- CÁC CÔNG CỤ CHUYÊN DỤNG CHO AI ---
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

# --- LOGIC CHATBOT (GEMINI) ---
def show_chatbot():
    google_api_key = None
    try:
        google_api_key = st.secrets.get("GOOGLE_API_KEY")
    except (StreamlitAPIException, StreamlitSecretNotFoundError):
        google_api_key = os.environ.get("GOOGLE_API_KEY")

    if not google_api_key:
        st.error("Không tìm thấy Google API Key. Vui lòng thiết lập trong tệp .streamlit/secrets.toml (local) hoặc trong Config Vars (Heroku).")
        return

    try:
        genai.configure(api_key=google_api_key)
    except Exception as e:
        st.error(f"Lỗi khi cấu hình Gemini API Key: {e}")
        return

    tools = [find_products, count_products_by_type]
    model_name = rfile("module_gemini.txt").strip() or "gemini-1.5-pro-latest"
    base_system_prompt = rfile("system_data/01.system_trainning.txt")
    all_products_data = get_all_products_as_dicts()
    
    # Nạp system prompt + thông tin sản phẩm hiện hành
    if all_products_data:
        product_data_string = "\nDưới đây là toàn bộ danh sách sản phẩm hệ thống mà bạn cần ghi nhớ để trả lời người dùng. Thông tin này là kiến thức nền của bạn:\n\n"
        for product in all_products_data:
            product_data_string += "--- BẮT ĐẦU SẢN PHẨM ---\n"
            product_data_string += product.get('original_content', '')
            product_data_string += "\n--- KẾT THÚC SẢN PHẨM ---\n\n"
        system_prompt = base_system_prompt + product_data_string
    else:
        system_prompt = base_system_prompt

    model = genai.GenerativeModel(
        model_name=model_name,
        tools=tools,
        system_instruction=system_prompt,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
    )

    # Greeting động theo sản phẩm hiện tại
    if "chat" not in st.session_state or "messages" not in st.session_state:
        greeting = make_greeting_message(all_products_data)
        st.session_state.chat = model.start_chat()
        st.session_state.messages = [{"role": "assistant", "content": greeting}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Nhập nội dung trao đổi ở đây !"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Trợ lý đang suy nghĩ..."):
                try:
                    response = st.session_state.chat.send_message(prompt)
                    while response.candidates[0].content.parts[0].function_call:
                        function_call = response.candidates[0].content.parts[0].function_call
                        function_name = function_call.name
                        function_args = dict(function_call.args)
                        
                        available_functions = {"find_products": find_products, "count_products_by_type": count_products_by_type}
                        function_to_call = available_functions[function_name]
                        function_response = function_to_call(**function_args)
                        
                        response = st.session_state.chat.send_message(
                            genai.Part.from_function_response(
                                name=function_name,
                                response={"result": function_response}
                            )
                        )
                    
                    final_response = response.text
                    st.markdown(final_response)
                    st.session_state.messages.append({"role": "assistant", "content": final_response})
                except Exception as e:
                    st.error(f"Đã xảy ra lỗi với Gemini: {e}")

# --- CÁC HÀM GIAO DIỆN ---
def show_main_page():
    st.subheader("✨ Các bài viết nổi bật")
    default_images = ["03bai_viet/article_images/pic1.jpg", "03bai_viet/article_images/pic2.jpg", "03bai_viet/article_images/pic3.jpg"]
    default_titles = ["Tiêu đề bài viết 1", "Tiêu đề bài viết 2", "Tiêu đề bài viết 3"]
    image_paths = [path if os.path.exists(path) else f"https://placehold.co/400x267/a3e635/44403c?text=Thiếu+ảnh+{i+1}" for i, path in enumerate(default_images)]
    article_titles = load_config_data("03bai_viet/config_titles.txt", default_titles)
    
    col1, col2, col3 = st.columns(3, gap="medium")
    for i, col in enumerate([col1, col2, col3]):
        with col:
            st.image(image_paths[i], use_container_width=True)
            if st.button(article_titles[i], use_container_width=True, key=f"btn{i+1}"):
                st.session_state.view = f"article_{i+1}"
                st.rerun()

    st.divider()
    if os.path.exists("system_data/logo.png"):
        logo_col1, logo_col2, logo_col3 = st.columns([1,1,1])
        with logo_col2:
            st.image("system_data/logo.png", use_container_width=True)

    st.markdown(f"<h2 style='text-align: center;'>{rfile('system_data/00.xinchao.txt') or 'Chào mừng đến với Trợ lý AI'}</h2>", unsafe_allow_html=True)
    show_chatbot()

def show_article_page(article_number):
    if st.button("⬅️ Quay về Trang chủ"): 
        st.session_state.view = "main"
        st.rerun()
    st.divider()
    try:
        with open(f"03bai_viet/bai_viet_0{article_number}.html", "r", encoding="utf-8") as f:
            html(f.read(), height=800, scrolling=True)
    except FileNotFoundError:
        st.error(f"Lỗi: Không tìm thấy file bài viết số {article_number}.")

def main():
    st.set_page_config(page_title="Trợ lý AI", page_icon="🤖", layout="wide")

    with st.sidebar:
        st.title("⚙️ Tùy chọn")
        if st.button("🗑️ Xóa cuộc trò chuyện"):
            if "chat" in st.session_state: del st.session_state.chat
            if "messages" in st.session_state: del st.session_state.messages
            st.session_state.view = "main"
            st.rerun()
        st.divider()
        st.markdown("Một sản phẩm của [Lê Đắc Chiến](https://ledacchien.com)")

    st.markdown("""<style>
        [data-testid="stToolbar"], header, #MainMenu {visibility: hidden !important;}
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stChatMessageContent-user"]) { justify-content: flex-end; }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageContent-user"]) { flex-direction: row-reverse; }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage {
            height: 150px;
            width: 100%;
            overflow: hidden;
            border-radius: 0.5rem;
        }
        .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage img {
            height: 100%;
            width: 100%;
            object-fit: cover;
        }
        [data-testid="stChatMessages"] {
            min-height: 70vh;
        }
        @media (max-width: 768px) {
            .st-emotion-cache-1v0mbdj > div > div > div > div > div[data-testid="stVerticalBlock"] .stImage {
                height: 100px;
            }
            .stButton > button {
                font-size: 0.8rem;
                padding: 0.3em 0.5em;
            }
        }
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
