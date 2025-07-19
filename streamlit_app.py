import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import glob
import os

def rfile(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def get_all_products_as_dicts():
    product_data_folder = "product_data"
    files = sorted(glob.glob(os.path.join(product_data_folder, "*.txt")))
    products = []
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        products.append({
            "filename": os.path.basename(file),
            "original_content": content
        })
    return products

# Cấu hình model
model_name = rfile("module_gemini.txt").strip() or "gemini-1.5-pro-latest"
base_system_prompt = rfile("system_data/01.system_trainning.txt")
all_products_data = get_all_products_as_dicts()
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
    system_instruction=system_prompt,
    safety_settings={
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
)

# Lời chào lấy từ file assistant (02.assistant.txt)
if "chat" not in st.session_state or "messages" not in st.session_state:
    assistant_greeting = rfile("system_data/02.assistant.txt") or "Em kính chào anh/chị, Em là Flowly - Trợ lý AI Agent tại ledacchien.com. Anh/chị cần tư vấn về khóa học hoặc dịch vụ nào, em sẽ hỗ trợ ngay ạ!"
    st.session_state.chat = model.start_chat()
    st.session_state.messages = [{"role": "assistant", "content": assistant_greeting}]

# Hiển thị logo nếu có
if os.path.exists("system_data/logo.png"):
    st.image("system_data/logo.png", width=100)

# Lịch sử hội thoại
st.markdown("<h3 style='color:#009688;'>Flowly - Trợ lý AI Agent</h3>", unsafe_allow_html=True)

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"<div style='color:#1a237e; margin-bottom:6px'><b>Bạn:</b> {msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='color:#263238; margin-bottom:6px'><b>Flowly:</b> {msg['content']}</div>", unsafe_allow_html=True)

# Ô nhập liệu và gửi
user_input = st.text_input("Nhập nội dung trò chuyện với Flowly...", key="user_input")

if st.button("Gửi", key="send_button") or (user_input and st.session_state.get("user_input_sent") != user_input):
    if user_input.strip():
        st.session_state.messages.append({"role": "user", "content": user_input})
        # Trả lời AI
        chat = st.session_state.chat
        response = ""
        for chunk in chat.send_message(user_input, stream=True):
            response += chunk.text
            st.session_state.messages[-1]["stream"] = response  # Xem thử nếu muốn hiển thị dần
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.user_input_sent = user_input
        st.experimental_rerun()
