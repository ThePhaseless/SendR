/**
 * @param {{ set: (options: Record<string, unknown>) => void }} config
 */

module.exports = function configureKarma(config) {
  config.set({
    browsers: ["ChromeHeadlessNoSandbox"],
    customLaunchers: {
      ChromeHeadlessNoSandbox: {
        base: "ChromeHeadless",
        flags: ["--no-sandbox", "--disable-dev-shm-usage"],
      },
    },
    frameworks: ["jasmine", "@angular-devkit/build-angular"],
    plugins: [
      require("karma-chrome-launcher"),
      require("karma-jasmine"),
      require("@angular-devkit/build-angular/plugins/karma"),
    ],
  });
};
