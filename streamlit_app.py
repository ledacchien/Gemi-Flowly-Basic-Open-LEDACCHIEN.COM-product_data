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

# --- LOGIC CHATBOT VỚI GEMINI ---
def show_chatbot():
    # Sử dụng Google API Key
    google_api_key = st.secrets.get("GOOGLE_API_KEY")
    if not google_api_key:
        st.error("Chưa có Google API Key. Vui lòng thiết lập trong Streamlit Secrets.")
        return
    try:
        genai.configure(api_key=google_api_key)
    except Exception as e:
        st.error(f"Lỗi cấu hình Gemini: {e}")
        return

    # Đọc model từ file module_gemini.txt
    model_name = rfile("module_gemini.txt").strip() or "gemini-1.5-pro"
    
    # Khởi tạo model và lịch sử chat
    if "gemini_model" not in st.session_state:
        st.session_state.gemini_model = genai.GenerativeModel(model_name=model_name)
    if "messages" not in st.session_state:
        initial_message = rfile("02.assistant.txt") or "Tôi có thể giúp gì cho bạn?"
        st.session_state.messages = [{"role": "assistant", "content": initial_message}]

    # Hiển thị các tin nhắn đã có
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Xử lý tin nhắn mới
    if prompt := st.chat_input("Bạn nhập nội dung cần trao đổi ở đây nhé?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # Gửi tin nhắn đến Gemini và xử lý phản hồi
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        user_prompt = st.session_state.messages[-1]["content"]
        
        chat_session = st.session_state.gemini_model.start_chat()
        
        # Đọc file huấn luyện và tất cả file sản phẩm
        system_context = [rfile("01.system_trainning.txt")]
        product_data_dir = "product_data"
        if os.path.isdir(product_data_dir):
            product_files = glob.glob(os.path.join(product_data_dir, '*.txt'))
            for file_path in product_files:
                system_context.append(rfile(file_path))
        
        # Ghép toàn bộ dữ liệu và câu hỏi
        full_prompt = (
            "\n\n---\n\n".join(filter(None, system_context)) +
            "\n\n---\n\nHỏi: " +
            user_prompt
        )

        with st.chat_message("assistant"):
            with st.spinner("Trợ lý đang suy nghĩ..."):
                try:
                    # Gửi yêu cầu và tắt function calling để đảm bảo an toàn
                    response = chat_session.send_message(
                        full_prompt,
                        tool_config={'function_calling_config': {'mode': 'none'}}
                    )
                    final_response = response.text
                    st.markdown(final_response)
                    st.session_state.messages.append({"role": "assistant", "content": final_response})
                except Exception as e:
                    st.error(f"Đã xảy ra lỗi với Gemini: {e}")

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