FROM ubuntu:24.04 AS build
ARG LLAMA_VERSION=b11819
RUN apt-get update && apt-get install -y --no-install-recommends git cmake build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${LLAMA_VERSION} https://github.com/ggml-org/llama.cpp /src
RUN cmake -S /src -B /src/build -DGGML_NATIVE=OFF -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_TESTS=OFF -DLLAMA_CURL=OFF && cmake --build /src/build --target llama-server -j 2
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/build/bin/llama-server /usr/local/bin/llama-server
RUN useradd --uid 10002 --create-home inference
USER inference
ENTRYPOINT ["llama-server"]
