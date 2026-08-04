# Sandbox image for cbias_config.py. The CBIAS Feedback data is CSV, not xlsx (converted during
# anonymisation - see anonymize_cbias_data.py), so no openpyxl dependency is needed here.
# scipy/scikit-learn/nltk/seaborn/textstat are DIVERGER_PLAN.md §10's interim provisioning fix -
# Run 8 measured only 1/8 judged angles able to run on the prior numpy/pandas/matplotlib-only
# image against what ideation's `requires` field actually asked for. Not a general-purpose
# allowance: keep this list matched to observed `requires` values, not a guess at what might help.
# Build with: docker build --target cbias-analysis -t cbias-analysis:latest .
FROM python:3.13-slim AS cbias-analysis

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pre-install Python packages (must match AVAILABLE_LIBRARIES in cbias_config.py)
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    scipy \
    scikit-learn \
    nltk \
    seaborn \
    textstat

# nltk corpora are fetched at runtime by nltk.download(), not by `pip install nltk` - with
# --network none in DOCKER_SANDBOX_FLAGS that fails on first use unless baked in at build time
# (DIVERGER_PLAN.md §10). punkt/punkt_tab (tokenization) and stopwords cover the standard entry
# point for the free-text feedback/abstract fields this config's angles reach for.
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"

WORKDIR /work


# Default sandbox image for bioimage_config.py.
# Build with: docker build -t bia-analysis:latest .
FROM python:3.13-slim AS bia-analysis

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pre-install Python packages (must match AVAILABLE_LIBRARIES in bioimage_config.py)
RUN pip install --no-cache-dir \
    numpy \
    scipy \
    scikit-image \
    scikit-learn \
    pandas \
    matplotlib \
    bioio \
    bioio-tifffile

WORKDIR /work