FROM bench-base:py312

# Disable proxy for pip installations
RUN HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" pip install \
    pandas \
    requests \
    scipy \
    matplotlib \
    numpy \
    scikit-learn \
    pyarrow \
    psutil \
    lxml \
    beautifulsoup4 \
    seaborn \
    pandas-datareader \
    nltk \
    dask \
    tensorflow-cpu \
    flask \
    Flask-Mail \
    PyMySQL \
    -i https://pypi.org/simple \
    --trusted-host pypi.org

# Fallback: if main install fails, retry with alternative mirror
RUN if ! python -c "import scipy" 2>/dev/null; then \
    pip install scipy matplotlib seaborn pandas-datareader nltk dask tensorflow-cpu \
    Flask-Mail PyMySQL \
    -i https://pypi.org/simple/ --trusted-host pypi.org; \
    fi

# Use sitecustomize.py to auto-register PyMySQL as MySQLdb when Python starts
# This allows `import MySQLdb` to work without installing mysqlclient C extension
RUN python3 -c "import site; print(site.getsitepackages()[0])" > /tmp/sitepath.txt && \
    SITEPATH=$(cat /tmp/sitepath.txt) && \
    echo "import pymysql; pymysql.install_as_MySQLdb()" >> "$SITEPATH/sitecustomize.py"

# Download nltk data (prevent error on first use)
RUN python3 -c "import nltk; nltk.download('stopwords', quiet=True)"

# Verify critical dependencies installed successfully
RUN python3 -c "import MySQLdb; print('MySQLdb OK')" && \
    python3 -c "import flask_mail; print('flask_mail OK')"