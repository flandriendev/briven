# Use the pre-built base image for Briven
# FROM briven-base:local
# FROM briven/briven-base:testing
FROM briven/briven-base:latest

# Check if the argument is provided, else throw an error
ARG BRANCH
RUN if [ -z "$BRANCH" ]; then echo "ERROR: BRANCH is not set!" >&2; exit 1; fi
ENV BRANCH=$BRANCH

# Copy filesystem files to root
COPY ./fs/ /

# pre installation steps
RUN bash /ins/pre_install.sh $BRANCH

# install Briven
RUN bash /ins/install_briven.sh $BRANCH

# install additional software
RUN bash /ins/install_additional.sh $BRANCH

# cleanup repo and install Briven without caching, this speeds up builds
ARG CACHE_DATE=none
RUN echo "cache buster $CACHE_DATE" && bash /ins/install_briven2.sh $BRANCH

# post installation steps
RUN bash /ins/post_install.sh $BRANCH

# Expose ports
EXPOSE 22 80 9000-9009

RUN chmod +x /exe/initialize.sh /exe/run_briven.sh /exe/run_searxng.sh /exe/run_tunnel_api.sh

# initialize runtime and switch to supervisord
CMD ["/exe/initialize.sh", "$BRANCH"]
