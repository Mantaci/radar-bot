// Cloudflare Worker: по Cron Trigger проверяет веб-превью канала,
// матчит термины и шлёт новые посты в Telegram. Состояние — в KV.
// Все значимые параметры — в env (Worker secrets), в коде ничего конкретного.

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36";

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env));
  },

  // Ручной триггер для проверки: /run?key=<CHAT_ID>
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === "/run") {
      if (url.searchParams.get("key") !== String(env.CHAT_ID)) {
        return new Response("forbidden", { status: 403 });
      }
      const summary = await run(env);
      return new Response(summary, { status: 200 });
    }
    return new Response("ok", { status: 200 });
  },
};

async function run(env) {
  const source = env.SOURCE;
  const terms = env.TERMS.split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);

  const posts = await fetchPosts(source);
  if (!posts.length) return "no posts";

  const last = parseInt((await env.STATE.get("last_post_id")) || "0", 10);
  const maxId = Math.max(...posts.map((p) => p.id));

  // Первый запуск: запоминаем текущий максимум, без рассылки бэклога.
  if (!last) {
    await env.STATE.put("last_post_id", String(maxId));
    return `baseline ${maxId}`;
  }

  const fresh = posts.filter((p) => p.id > last).sort((a, b) => a.id - b.id);
  let sent = 0;
  for (const p of fresh) {
    const hits = matched(p.text, terms);
    if (hits.length) {
      await send(env, formatMessage(p, hits));
      sent++;
    }
  }
  if (fresh.length) {
    await env.STATE.put(
      "last_post_id",
      String(Math.max(...fresh.map((p) => p.id)))
    );
  }
  return `new=${fresh.length} sent=${sent}`;
}

async function fetchPosts(source) {
  const resp = await fetch(`https://t.me/s/${source}`, {
    headers: { "user-agent": UA },
  });
  if (!resp.ok) return [];

  const posts = [];
  let current = null;
  const rewriter = new HTMLRewriter()
    .on("div[data-post]", {
      element(el) {
        const dp = el.getAttribute("data-post");
        if (!dp) return;
        const id = parseInt(dp.split("/").pop(), 10);
        if (Number.isNaN(id)) return;
        current = { id, text: "", link: `https://t.me/${dp}` };
        posts.push(current);
      },
    })
    .on(".tgme_widget_message_text", {
      text(t) {
        if (current) current.text += t.text;
      },
    });

  await rewriter.transform(resp).arrayBuffer();
  return posts;
}

// Каждый term — основа слова: матч от границы слова (Unicode-aware через
// lookbehind \p{L}) и дальше любые буквы. Ловит падежи, не цепляет слово
// изнутри. В JS \b/\w не работают с кириллицей, поэтому \p{L}.
function matched(text, terms) {
  const out = [];
  for (const term of terms) {
    const re = new RegExp("(?<!\\p{L})" + escapeRe(term) + "[\\p{L}]*", "giu");
    const ms = text.match(re);
    if (ms) for (const m of ms) if (!out.includes(m)) out.push(m);
  }
  return out;
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function formatMessage(post, hits) {
  let body = post.text || "(пост без текста)";
  if (body.length > 3500) body = body.slice(0, 3500) + "…";
  return (
    `📍 <b>${esc(hits.join(", "))}</b>\n\n` +
    `${esc(body)}\n\n` +
    `<a href="${post.link}">Открыть пост</a>`
  );
}

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function send(env, html) {
  await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: env.CHAT_ID,
      text: html,
      parse_mode: "HTML",
      disable_web_page_preview: false,
    }),
  });
}
