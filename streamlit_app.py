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
        
        # Tạo một phiên chat mới mỗi lần để gửi toàn bộ ngữ cảnh
        chat_session = st.session_state.gemini_model.start_chat()
        
        # Bắt đầu với file huấn luyện hệ thống
        system_context = [rfile("01.system_trainning.txt")]

        # Tìm và đọc tất cả các file .txt trong thư mục product_data
        product_data_dir = "product_data"
        if os.path.isdir(product_data_dir):
            product_files = glob.glob(os.path.join(product_data_dir, '*.txt'))
            for file_path in product_files:
                system_context.append(rfile(file_path))
        
        # Ghép toàn bộ dữ liệu hệ thống và câu hỏi của người dùng
        full_prompt = (
            "\n\n---\n\n".join(filter(None, system_context)) + # Lọc bỏ các chuỗi rỗng
            "\n\n---\n\nHỏi: " +
            user_prompt
        )

        with st.chat_message("assistant"):
            with st.spinner("Trợ lý đang suy nghĩ..."):
                try:
                    # Gửi yêu cầu và TẮT tính năng function calling
                    response = chat_session.send_message(
                        full_prompt,
                        tool_config={'function_calling_config': {'mode': 'none'}}
                    )
                    final_response = response.text
                    st.markdown(final_response)
                    st.session_state.messages.append({"role": "assistant", "content": final_response})
                except Exception as e:
                    st.error(f"Đã xảy ra lỗi với Gemini: {e}")