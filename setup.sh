mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"luids.vn@gmail.com\"\n\
" > ~/.streamlit/credentials.toml

echo "\
[server]\n\
headless = true\n\
enableCORS=false\n\
port = $PORT\n\
\n\
[theme]\n\
base=\"light\"\n\
" > ~/.streamlit/config.toml