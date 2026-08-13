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

WORKDIR /work

# nltk corpora are fetched at runtime by nltk.download(), not by `pip install nltk` - with
# --network none in DOCKER_SANDBOX_FLAGS that fails on first use unless baked in at build time
# (DIVERGER_PLAN.md §10). punkt/punkt_tab (tokenization) and stopwords cover the standard entry
# point for the free-text feedback/abstract fields this config's angles reach for. cmudict
# (Live Issue 15 - textstat's syllable counter reaches for it on every readability angle, a
# recurring family), wordnet and averaged_perceptron_tagger (POS-tagging angles, seen once so
# far) are baked in too so the same runtime-download failure doesn't recur for these corpora.
# Live Issue 22: modern nltk resolves POS tagging to the `_eng`-suffixed resource name, not the
# bare one - baking averaged_perceptron_tagger alone left pos_tag() silently unable to find data
# at runtime (caught and swallowed by the generated script, not a crash), so a script computing
# five metrics quietly delivered four. Same moving-target list as §10 warns about - bake both
# names rather than assuming one covers the other.
# Must run with cwd != "/" (hence WORKDIR above): nltk 3.10's import-hijacking guard
# (nltk/inisec.py, CWE-427 mitigation) blocks any import whose resolved path is "relative to"
# the cwd, and every absolute path is trivially "relative to" root - triggers a spurious block
# on nltk's own `import locale` if this runs before WORKDIR is set. `-P`/PYTHONSAFEPATH does not
# help here: the guard reads Path.cwd() directly, not sys.path.
#
# Live Issue 14: without an explicit download_dir, this lands in /root/nltk_data (this RUN executes
# as root, no HOME override yet) - a path that is BOTH unreadable (mode 700) AND absent from the
# search list DOCKER_SANDBOX_FLAGS' runtime user actually uses (--user 1000:1000, HOME=/tmp, so
# nltk.data.path is [/tmp/nltk_data (empty tmpfs), /usr/local/nltk_data, /usr/local/share/nltk_data,
# /usr/local/lib/nltk_data, /usr/share/nltk_data, ...] - /root/nltk_data is never in it regardless of
# HOME). Fixed by downloading straight into a system-wide path that IS unconditionally on that list,
# then making it world-readable so the non-root runtime user can actually open it; NLTK_DATA is set
# as a second, env-based way to reach the same directory that does not depend on nltk's default
# search-path construction at all. Verified against a real container: see DIVERGER_PLAN.md Issue 14.
ENV NLTK_DATA=/usr/local/share/nltk_data
RUN python -P -c "\
import nltk; \
nltk.download('punkt', download_dir='$NLTK_DATA'); \
nltk.download('punkt_tab', download_dir='$NLTK_DATA'); \
nltk.download('stopwords', download_dir='$NLTK_DATA'); \
nltk.download('cmudict', download_dir='$NLTK_DATA'); \
nltk.download('wordnet', download_dir='$NLTK_DATA'); \
nltk.download('averaged_perceptron_tagger', download_dir='$NLTK_DATA'); \
nltk.download('averaged_perceptron_tagger_eng', download_dir='$NLTK_DATA')" \
    && chmod -R a+rX "$NLTK_DATA"


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