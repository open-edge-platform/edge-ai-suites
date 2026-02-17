FROM eclipse-temurin:17

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

COPY mdpnp/interop-lab/demo-apps/flat /opt/mdpnp/flat
WORKDIR /opt/mdpnp/flat
ENV LD_LIBRARY_PATH /opt/mdpnp/flat
ENV RTI_LICENSE_FILE /opt/mdpnp/flat/OpenICE_license.dat

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]