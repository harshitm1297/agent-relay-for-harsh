# Homework 3 answers

1. **Agents claim tasks from a DB through an HTTP API.** The relay stores identities, tasks, leases, results, and delivery attempts; agents execute work outside the relay.
2. **`completed`.** After the recipient submits the result, the sender retrieves the task with status `completed` and the output.
3. **`-p`.** Docker's `-p HOST:CONTAINER` option publishes a container port to the host.
4. **`postgres`.** Docker Compose DNS resolves a service by its service name; `localhost` inside the API container refers to that API container.
5. **Deployment.** The Deployment controller maintains the requested application replicas and manages rolling updates.
6. **Keep the existing version running and stop the deployment.** The deployment job depends on the test job, so a failure prevents the new image from being built or rolled out.
