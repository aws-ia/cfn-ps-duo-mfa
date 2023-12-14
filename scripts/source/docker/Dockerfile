FROM public.ecr.aws/amazonlinux/amazonlinux:latest

COPY run_duo.sh /app/
RUN set -xe && \
    yum install gcc make zlib-devel libffi-devel tar wget gzip perl shadow-utils.x86_64 procps diffutils -y && \
    wget -O jq https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64 && \
    chmod +x ./jq && \
    cp jq /usr/bin && \
    wget https://dl.duosecurity.com/duoauthproxy-latest-src.tgz && \
    tar xzf duoauthproxy-*.tgz && \
    rm duoauthproxy-*.tgz && \
    cd duoauthproxy-*-src && \
    make && \
    cd /duo*/duo*/  && \
    ./install --install-dir=/opt/duoauthproxy --service-user=nobody --create-init-script=yes --log-group=duo_authproxy_grp && \
    rm -fr /duo* && \
    yum remove kernel-headers wget -y && \
    yum update -y && \
    chmod +x /app/run_duo.sh

EXPOSE 1812/udp
ENTRYPOINT /app/run_duo.sh
