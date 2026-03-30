import { defineConfig } from "orval";

export default defineConfig({
  sendr: {
    input: {
      target: "../openapi.json",
    },
    output: {
      mode: "tags-split",
      target: "src/app/api/endpoints",
      schemas: "src/app/api/model",
      client: "angular",
      override: {
        angular: {
          provideIn: "root",
          retrievalClient: "both",
        },
      },
    },
  },
});
