const fs = require("fs");

const bundlePath = process.argv[2];
const src = fs.readFileSync(bundlePath, "utf8");

const SCRIPT_SRC = "https://api.flyrank.example/public/widget/abc/widget.js?v=3";
const PAGE_HREF = "https://customer-site.example/contact";
const PAGE_ORIGIN = "https://customer-site.example";

const captured = { config: null, submit: null };
const createdForms = [];
const createdInputs = [];

function makeElement(tag) {
  const el = {
    tagName: tag.toUpperCase(),
    style: {},
    textContent: "",
    innerHTML: "",
    type: "",
    name: "",
    value: "",
    placeholder: "",
    tabIndex: 0,
    autocomplete: "",
    disabled: false,
    appendChild() {},
    setAttribute() {},
    addEventListener() {},
    querySelectorAll() {
      return tag === "form" ? createdInputs : [];
    },
  };
  if (tag === "form") createdForms.push(el);
  if (tag === "input") createdInputs.push(el);
  return el;
}

const document = {
  currentScript: {
    src: SCRIPT_SRC,
    getAttribute() {
      return null;
    },
  },
  createElement: makeElement,
  getElementById() {
    return { style: {}, textContent: "" };
  },
  body: { appendChild() {} },
};

class FakeXHR {
  open(method, url) {
    if (method === "GET") captured.config = new URL(url, PAGE_HREF).href;
    else if (method === "POST") captured.submit = new URL(url, PAGE_HREF).href;
  }

  setRequestHeader() {}

  send() {
    this.status = 200;
    this.responseText = JSON.stringify({
      brand_color: "#2563eb",
      button_text: "Get a Quote",
      fields: ["name", "email"],
      success_message: "Thanks!",
      honeypot_field: "_hp_test",
    });
    if (typeof this.onload === "function") this.onload();
  }
}

class FakeFormData {
  constructor(form) {
    this._inputs =
      form && form.querySelectorAll ? form.querySelectorAll("input") : [];
  }

  forEach(cb) {
    for (const input of this._inputs) {
      if (input.type !== "hidden" && input.name) cb(input.value, input.name);
    }
  }
}

global.document = document;
global.window = { location: { href: PAGE_HREF, origin: PAGE_ORIGIN } };
global.location = { href: PAGE_HREF, origin: PAGE_ORIGIN };
global.XMLHttpRequest = FakeXHR;
global.FormData = FakeFormData;

eval(src);

if (createdForms.length === 0) {
  console.error("no form created");
  process.exit(3);
}
const form = createdForms[0];
if (typeof form.onsubmit !== "function") {
  console.error("no onsubmit handler");
  process.exit(4);
}
form.onsubmit({ preventDefault() {} });

console.log(JSON.stringify(captured));
process.exit(0);
