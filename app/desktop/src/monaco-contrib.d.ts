// Monaco 0.57 exposes `suggestController` via its package exports wildcard,
// without a companion `.d.ts`. Keep this side-effect-only declaration local
// so strict TypeScript accepts the dynamic import in `DocumentEditor.tsx`.
declare module "monaco-editor/editor/contrib/suggest/browser/suggestController";
