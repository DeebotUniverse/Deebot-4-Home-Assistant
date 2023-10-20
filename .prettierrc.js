/** @type {import("prettier").Config} */
module.exports = {
  plugins: [require.resolve("prettier-plugin-sort-json")],
  jsonRecursiveSort: true,
};
