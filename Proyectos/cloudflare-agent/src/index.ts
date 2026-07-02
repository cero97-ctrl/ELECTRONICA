import { PDFDocument, rgb, StandardFonts } from 'pdf-lib';

export interface Env {
  GROQ_API_KEY: string;
  OPENROUTER_API_KEY: string;
  GOOGLE_API_KEY: string;
}

interface Item {
  description: string;
  quantity: number;
  price: number;
}

interface QuoteRequest {
  clientName: string;
  clientEmail: string;
  items: Item[];
  notes?: string;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method;

    // CORS Headers for accessibility
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    if (method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // 1. Endpoint: Servir la UI del Agente (GET /)
      if (url.pathname === '/' && method === 'GET') {
        return new Response(UI_HTML, {
          headers: { 'Content-Type': 'text/html; charset=utf-8', ...corsHeaders }
        });
      }

      // 2. Endpoint: Diagnóstico de Estado (GET /status)
      if (url.pathname === '/status' && method === 'GET') {
        const statusInfo = {
          status: 'ok',
          agent: 'Cloudflare Serverless Agent',
          version: '1.1.0',
          endpoints: {
            ui: 'GET /',
            status: 'GET /status',
            chat: 'POST /chat { message, provider? }',
            quote: 'POST /quote { clientName, clientEmail, items: [{description, quantity, price}], notes? }'
          },
          configured_apis: {
            groq: !!env.GROQ_API_KEY,
            openrouter: !!env.OPENROUTER_API_KEY,
            google: !!env.GOOGLE_API_KEY
          }
        };
        return new Response(JSON.stringify(statusInfo, null, 2), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // 3. Endpoint: Chat con LLM (POST /chat)
      if (url.pathname === '/chat' && method === 'POST') {
        const body = await request.json() as { message: string; provider?: string };
        const { message, provider = 'groq' } = body;

        if (!message) {
          return new Response(JSON.stringify({ error: 'Falta el parámetro "message"' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        if (provider === 'groq') {
          if (!env.GROQ_API_KEY) {
            throw new Error('La clave GROQ_API_KEY no está configurada.');
          }
          const groqResponse = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${env.GROQ_API_KEY}`
            },
            body: JSON.stringify({
              model: 'qwen/qwen3.6-27b',
              messages: [
                { role: 'system', content: 'Eres un agente de cotización automatizado. Responde de forma profesional, clara y en español.' },
                { role: 'user', content: message }
              ]
            })
          });

          if (!groqResponse.ok) {
            const errText = await groqResponse.text();
            throw new Error(`Error de Groq API (${groqResponse.status}): ${errText}`);
          }

          const data: any = await groqResponse.json();
          const reply = data.choices[0].message.content;

          return new Response(JSON.stringify({ provider: 'groq', response: reply }), {
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });

        } else if (provider === 'openrouter') {
          if (!env.OPENROUTER_API_KEY) {
            throw new Error('La clave OPENROUTER_API_KEY no está configurada.');
          }
          const orResponse = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${env.OPENROUTER_API_KEY}`,
              'HTTP-Referer': 'https://cloudflare-agent.cero.dev',
              'X-Title': 'Cloudflare Serverless Agent'
            },
            body: JSON.stringify({
              model: 'google/gemini-2.5-flash',
              messages: [
                { role: 'system', content: 'Eres un agente experto. Responde en español.' },
                { role: 'user', content: message }
              ]
            })
          });

          if (!orResponse.ok) {
            const errText = await orResponse.text();
            throw new Error(`Error de OpenRouter API (${orResponse.status}): ${errText}`);
          }

          const data: any = await orResponse.json();
          const reply = data.choices[0].message.content;

          return new Response(JSON.stringify({ provider: 'openrouter', response: reply }), {
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });

        } else if (provider === 'google') {
          if (!env.GOOGLE_API_KEY) {
            throw new Error('La clave GOOGLE_API_KEY no está configurada.');
          }
          const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${env.GOOGLE_API_KEY}`;
          const gResponse = await fetch(geminiUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              contents: [{
                parts: [{ text: message }]
              }]
            })
          });

          if (!gResponse.ok) {
            const errText = await gResponse.text();
            throw new Error(`Error de Google Gemini API (${gResponse.status}): ${errText}`);
          }

          const data: any = await gResponse.json();
          const reply = data.candidates[0].content.parts[0].text;

          return new Response(JSON.stringify({ provider: 'google', response: reply }), {
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });

        } else {
          return new Response(JSON.stringify({ error: `Proveedor no soportado: ${provider}` }), {
            status: 400,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }
      }

      // 4. Endpoint: Generación de Cotización (POST /quote)
      if (url.pathname === '/quote' && method === 'POST') {
        const body = await request.json() as QuoteRequest;
        const { clientName, clientEmail, items, notes } = body;

        if (!clientName || !clientEmail || !items || !Array.isArray(items) || items.length === 0) {
          return new Response(JSON.stringify({ error: 'Faltan parámetros requeridos: clientName, clientEmail, items.' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        // Crear documento PDF
        const pdfDoc = await PDFDocument.create();
        const page = pdfDoc.addPage([600, 500]);
        const { width, height } = page.getSize();
        
        // Embeber fuentes estándar
        const helveticaBold = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
        const helvetica = await pdfDoc.embedFont(StandardFonts.Helvetica);

        // Cabecera de la Cotización
        page.drawText('COTIZACIÓN AUTOMÁTICA - AGENTE SERVERLESS', {
          x: 50,
          y: height - 50,
          size: 18,
          font: helveticaBold,
          color: rgb(0, 0.4, 0.7),
        });

        page.drawText(`Fecha: ${new Date().toLocaleDateString()}`, {
          x: 50,
          y: height - 70,
          size: 10,
          font: helvetica,
        });

        // Información del Cliente
        page.drawText('INFORMACIÓN DEL CLIENTE:', {
          x: 50,
          y: height - 100,
          size: 11,
          font: helveticaBold,
        });
        page.drawText(`Nombre: ${clientName}`, { x: 50, y: height - 115, size: 10, font: helvetica });
        page.drawText(`Email: ${clientEmail}`, { x: 50, y: height - 130, size: 10, font: helvetica });

        // Tabla de ítems
        let yOffset = height - 170;
        page.drawText('Descripción', { x: 50, y: yOffset, size: 10, font: helveticaBold });
        page.drawText('Cant.', { x: 340, y: yOffset, size: 10, font: helveticaBold });
        page.drawText('Precio U.', { x: 400, y: yOffset, size: 10, font: helveticaBold });
        page.drawText('Total', { x: 480, y: yOffset, size: 10, font: helveticaBold });

        // Línea divisoria cabecera tabla
        page.drawLine({
          start: { x: 50, y: yOffset - 5 },
          end: { x: 540, y: yOffset - 5 },
          thickness: 1,
          color: rgb(0.7, 0.7, 0.7)
        });

        yOffset -= 20;
        let subtotal = 0;

        for (const item of items) {
          const itemTotal = item.quantity * item.price;
          subtotal += itemTotal;

          page.drawText(item.description, { x: 50, y: yOffset, size: 9, font: helvetica });
          page.drawText(String(item.quantity), { x: 340, y: yOffset, size: 9, font: helvetica });
          page.drawText(`$${item.price.toFixed(2)}`, { x: 400, y: yOffset, size: 9, font: helvetica });
          page.drawText(`$${itemTotal.toFixed(2)}`, { x: 480, y: yOffset, size: 9, font: helvetica });

          yOffset -= 15;
        }

        // Línea divisoria total
        page.drawLine({
          start: { x: 50, y: yOffset },
          end: { x: 540, y: yOffset },
          thickness: 1,
          color: rgb(0.7, 0.7, 0.7)
        });

        yOffset -= 20;
        page.drawText('TOTAL GENERAL:', {
          x: 340,
          y: yOffset,
          size: 11,
          font: helveticaBold,
          color: rgb(0.8, 0.1, 0.1),
        });
        page.drawText(`$${subtotal.toFixed(2)}`, {
          x: 480,
          y: yOffset,
          size: 11,
          font: helveticaBold,
          color: rgb(0.8, 0.1, 0.1),
        });

        // Notas / Términos
        if (notes) {
          yOffset -= 40;
          page.drawText('Notas / Términos y Condiciones:', { x: 50, y: yOffset, size: 9, font: helveticaBold });
          page.drawText(notes, { x: 50, y: yOffset - 15, size: 8, font: helvetica, color: rgb(0.3, 0.3, 0.3) });
        }

        // Pie de página
        page.drawText('Generado automáticamente por el Agente Cloudflare Worker.', {
          x: 50,
          y: 30,
          size: 8,
          font: helvetica,
          color: rgb(0.6, 0.6, 0.6)
        });

        const pdfBytes = await pdfDoc.save();

        return new Response(pdfBytes, {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': 'attachment; filename="cotizacion.pdf"',
            ...corsHeaders
          }
        });
      }

      // Ruta no encontrada
      return new Response(JSON.stringify({ error: 'Ruta no encontrada' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });

    } catch (error: any) {
      return new Response(JSON.stringify({ error: error.message || 'Error Interno del Agente' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }
  }
};

// =============================================================================
// HTML / CSS / JS EMBEBIDO PARA LA INTERFAZ DE USUARIO (GLASSMORPHIC WEB UI)
// =============================================================================
const UI_HTML = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agente Serverless — Consola de Control</title>
  <meta name="description" content="Interfaz web de administración del Agente AI en Cloudflare Workers para chat y generación de cotizaciones en PDF.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  
  <style>
    /* VARIABLES DE DISEÑO (AESTHETIC STYLE SYSTEM) */
    :root {
      --bg-color: #080c14;
      --panel-bg: rgba(17, 24, 39, 0.6);
      --border-color: rgba(255, 255, 255, 0.08);
      --primary-color: #00f2fe;
      --primary-gradient: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
      --accent-color: #ec4899;
      --text-primary: #f3f4f6;
      --text-secondary: #9ca3af;
      --user-msg-gradient: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
      --agent-msg-bg: rgba(31, 41, 55, 0.7);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Outfit', sans-serif;
      background-color: var(--bg-color);
      color: var(--text-primary);
      min-height: 100vh;
      overflow-x: hidden;
      position: relative;
    }

    /* EFECTOS DE FONDO DIVERGENTES (AMBIENT GLOWS) */
    body::before, body::after {
      content: '';
      position: absolute;
      width: 300px;
      height: 300px;
      border-radius: 50%;
      filter: blur(130px);
      z-index: -1;
      opacity: 0.35;
    }
    body::before {
      top: 10%;
      left: 15%;
      background: #00f2fe;
    }
    body::after {
      bottom: 15%;
      right: 10%;
      background: #ec4899;
    }

    /* CONTENEDOR PRINCIPAL */
    .app-container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      height: 100vh;
      max-height: 100vh;
    }

    /* CABECERA (HEADER COMPONENT) */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 20px;
      flex-shrink: 0;
    }

    .brand-section h1 {
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      background: var(--primary-gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand-section p {
      font-size: 0.85rem;
      color: var(--text-secondary);
    }

    .status-panel {
      display: flex;
      align-items: center;
      gap: 12px;
      background: var(--panel-bg);
      border: 1px solid var(--border-color);
      padding: 6px 12px;
      border-radius: 50px;
      backdrop-filter: blur(10px);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      background-color: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10b981;
      animation: pulse 1.8s infinite;
    }

    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 0.7; }
      50% { transform: scale(1.15); opacity: 1; }
      100% { transform: scale(0.9); opacity: 0.7; }
    }

    .status-panel span {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-secondary);
    }

    /* GRID LAYOUT DE CONTROL */
    .dashboard-grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 24px;
      flex-grow: 1;
      overflow: hidden;
      min-height: 0;
    }

    @media (max-width: 968px) {
      .dashboard-grid {
        grid-template-columns: 1fr;
        grid-template-rows: 1fr 1fr;
        overflow-y: auto;
      }
      .app-container {
        height: auto;
        max-height: none;
      }
    }

    /* PANELES GLASSMORPHIC */
    .glass-card {
      background: var(--panel-bg);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
      min-height: 0;
    }

    .card-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(255, 255, 255, 0.02);
      flex-shrink: 0;
    }

    .card-header h2 {
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--text-primary);
    }

    /* SECCIÓN 1: CHAT CONSOLE */
    .provider-selector {
      background: transparent;
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 0.8rem;
      outline: none;
      font-family: inherit;
      cursor: pointer;
    }
    .provider-selector option {
      background: var(--bg-color);
    }

    .chat-history {
      flex-grow: 1;
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 16px;
      background: rgba(0, 0, 0, 0.1);
    }

    .message {
      max-width: 80%;
      padding: 12px 16px;
      border-radius: 14px;
      font-size: 0.95rem;
      line-height: 1.5;
      animation: messageIn 0.3s ease-out forwards;
      white-space: pre-wrap;
    }

    @keyframes messageIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .message.user {
      align-self: flex-end;
      background: var(--user-msg-gradient);
      border-bottom-right-radius: 4px;
      box-shadow: 0 4px 12px rgba(2, 132, 199, 0.2);
    }

    .message.agent {
      align-self: flex-start;
      background: var(--agent-msg-bg);
      border: 1px solid var(--border-color);
      border-bottom-left-radius: 4px;
    }

    /* ESTILOS DEL BLOQUE DE PENSAMIENTO DE QWEN */
    .thinking-block {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 8px 12px;
      margin-bottom: 10px;
      font-size: 0.8rem;
      color: var(--text-secondary);
      font-family: 'JetBrains Mono', monospace;
    }
    .thinking-block summary {
      cursor: pointer;
      font-weight: 600;
      color: var(--primary-color);
      outline: none;
      user-select: none;
    }
    .thinking-block pre {
      margin-top: 8px;
      white-space: pre-wrap;
      overflow-x: auto;
      color: #a7f3d0;
      line-height: 1.4;
    }

    .chat-input-area {
      padding: 16px 20px;
      border-top: 1px solid var(--border-color);
      display: flex;
      gap: 12px;
      background: rgba(255, 255, 255, 0.01);
      flex-shrink: 0;
    }

    .chat-input-area input {
      flex-grow: 1;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px 16px;
      color: var(--text-primary);
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.2s;
    }

    .chat-input-area input:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 10px var(--primary-glow);
    }

    .btn {
      background: var(--primary-gradient);
      border: none;
      color: #000;
      font-weight: 600;
      padding: 12px 24px;
      border-radius: 8px;
      font-size: 0.95rem;
      cursor: pointer;
      transition: transform 0.2s, opacity 0.2s, box-shadow 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-family: inherit;
    }

    .btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4);
    }

    .btn:active {
      transform: translateY(0);
    }

    .btn:disabled {
      background: #4b5563;
      color: #9ca3af;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }

    /* SECCIÓN 2: QUOTE / COTIZADOR BUILDER */
    .form-content {
      flex-grow: 1;
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .form-group label {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .form-group input, .form-group textarea {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 10px 14px;
      color: var(--text-primary);
      font-size: 0.95rem;
      outline: none;
      font-family: inherit;
      transition: border-color 0.2s;
    }

    .form-group input:focus, .form-group textarea:focus {
      border-color: var(--primary-color);
    }

    .form-row-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }

    /* TABLA DINÁMICA DE ITEMS */
    .items-container {
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow: hidden;
    }

    .items-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }

    .items-table th {
      background: rgba(255, 255, 255, 0.03);
      padding: 10px 12px;
      text-align: left;
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 1px solid var(--border-color);
    }

    .items-table td {
      padding: 8px 12px;
      border-bottom: 1px solid var(--border-color);
      vertical-align: middle;
    }

    .items-table td input {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      border-radius: 4px;
      padding: 6px 10px;
      width: 100%;
      outline: none;
      font-family: inherit;
    }
    .items-table td input:focus {
      border-color: var(--primary-color);
    }

    .items-table td.qty-col { width: 80px; }
    .items-table td.price-col { width: 120px; }
    .items-table td.action-col { width: 50px; text-align: center; }

    .btn-delete {
      background: transparent;
      border: none;
      color: #ef4444;
      font-size: 1.1rem;
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
      transition: background 0.2s;
    }
    .btn-delete:hover {
      background: rgba(239, 68, 68, 0.15);
    }

    .table-actions {
      display: flex;
      justify-content: flex-end;
      padding: 12px;
      background: rgba(255, 255, 255, 0.01);
      border-top: 1px solid var(--border-color);
    }

    .btn-secondary {
      background: transparent;
      border: 1px solid var(--primary-color);
      color: var(--primary-color);
      padding: 8px 16px;
      font-size: 0.85rem;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.2s, color 0.2s;
      font-family: inherit;
    }
    .btn-secondary:hover {
      background: var(--primary-color);
      color: #000;
    }

    .totals-panel {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 20px;
      background: rgba(255, 255, 255, 0.02);
      border-top: 1px solid var(--border-color);
      border-bottom: 1px solid var(--border-color);
      flex-shrink: 0;
    }

    .totals-panel span.label {
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--text-secondary);
    }
    .totals-panel span.amount {
      font-size: 1.3rem;
      font-weight: 700;
      color: var(--primary-color);
    }

    .form-footer {
      padding: 16px 20px;
      display: flex;
      justify-content: flex-end;
      background: rgba(255, 255, 255, 0.01);
      flex-shrink: 0;
    }

    /* PERSONALIZACIÓN DE SCROLLBAR */
    ::-webkit-scrollbar {
      width: 6px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.15);
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.3);
    }

    /* ANIMACIÓN CARGANDO / SPINNER */
    .loader {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid rgba(0,0,0,0.3);
      border-radius: 50%;
      border-top-color: #000;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  </style>
</head>
<body>

  <div class="app-container">
    <!-- HEADER COMPONENT -->
    <header>
      <div class="brand-section">
        <h1>Console Agent</h1>
        <p>Orquestador Serverless en el Edge de Cloudflare</p>
      </div>
      <div class="status-panel">
        <div class="status-dot"></div>
        <span>Worker Online</span>
      </div>
    </header>

    <!-- GRID LAYOUT -->
    <div class="dashboard-grid">
      
      <!-- COLUMNA 1: CONSOLA DE CHAT (LEFT PANEL) -->
      <div class="glass-card" id="chat-card">
        <div class="card-header">
          <h2>Consola del Asistente</h2>
          <select id="model-provider" class="provider-selector">
            <option value="groq">Groq (Qwen 3.6 27B)</option>
            <option value="openrouter">OpenRouter (Gemini 2.5 Flash)</option>
            <option value="google">Google API (Gemini 1.5 Flash)</option>
          </select>
        </div>
        <div class="chat-history" id="chat-history">
          <!-- Mensaje inicial de bienvenida -->
          <div class="message agent">¡Hola! Soy tu asistente de cotizaciones serverless. Puedo ayudarte a responder consultas técnicas, organizar tus productos o estructurar tu cotización. Cuéntame qué necesitas.</div>
        </div>
        <div class="chat-input-area">
          <input type="text" id="chat-input" placeholder="Escribe un mensaje aquí..." id="chat-input-field">
          <button class="btn" id="btn-send" onclick="sendChatMessage()">
            <span>Enviar</span>
          </button>
        </div>
      </div>

      <!-- COLUMNA 2: GENERADOR DE COTIZACIONES (RIGHT PANEL) -->
      <div class="glass-card" id="quote-card">
        <div class="card-header">
          <h2>Generador de Cotizaciones</h2>
        </div>
        <div class="form-content">
          <!-- Datos cliente -->
          <div class="form-row-grid">
            <div class="form-group">
              <label for="client-name">Nombre del Cliente</label>
              <input type="text" id="client-name" placeholder="Ej. Juan Pérez">
            </div>
            <div class="form-group">
              <label for="client-email">Email del Cliente</label>
              <input type="email" id="client-email" placeholder="Ej. juan@example.com">
            </div>
          </div>

          <!-- Items dinámicos -->
          <div class="form-group">
            <label>Ítems de Cotización</label>
            <div class="items-container">
              <table class="items-table" id="items-table">
                <thead>
                  <tr>
                    <th>Descripción del Producto / Servicio</th>
                    <th class="qty-col">Cant.</th>
                    <th class="price-col">P. Unitario</th>
                    <th class="action-col"></th>
                  </tr>
                </thead>
                <tbody id="items-tbody">
                  <!-- Los renglones dinámicos se insertarán aquí por JS -->
                </tbody>
              </table>
              <div class="table-actions">
                <button class="btn-secondary" onclick="addNewItemRow()">+ Agregar Renglón</button>
              </div>
            </div>
          </div>

          <!-- Notas -->
          <div class="form-group">
            <label for="quote-notes">Notas / Términos y Condiciones</label>
            <textarea id="quote-notes" rows="3" placeholder="Ej. Tiempo estimado de entrega: 10 días hábiles. Validez de la oferta: 15 días."></textarea>
          </div>
        </div>

        <!-- Panel de Totales -->
        <div class="totals-panel">
          <span class="label">Total General:</span>
          <span class="amount" id="total-amount">$0.00</span>
        </div>

        <!-- Footer del Formulario -->
        <div class="form-footer">
          <button class="btn" id="btn-generate-pdf" onclick="generatePDFQuote()">
            <span>Generar y Descargar PDF</span>
          </button>
        </div>
      </div>

    </div>
  </div>

  <script>
    // Iniciar con un renglón por defecto en la tabla de ítems
    document.addEventListener("DOMContentLoaded", () => {
      addNewItemRow();
      
      // Permitir enviar con Enter en el chat
      document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          sendChatMessage();
        }
      });
    });

    // ==========================================
    // LÓGICA DE TABLA DINÁMICA (PRODUCTS GRID)
    // ==========================================
    function addNewItemRow() {
      const tbody = document.getElementById("items-tbody");
      const tr = document.createElement("tr");
      
      tr.innerHTML = \`
        <td><input type="text" class="item-desc" placeholder="Ej. Diseño de circuito impreso" oninput="calculateTotal()"></td>
        <td class="qty-col"><input type="number" class="item-qty" value="1" min="1" oninput="calculateTotal()"></td>
        <td class="price-col"><input type="number" class="item-price" value="0.00" step="0.01" min="0" oninput="calculateTotal()"></td>
        <td class="action-col"><button class="btn-delete" onclick="deleteRow(this)">✕</button></td>
      \`;
      
      tbody.appendChild(tr);
      calculateTotal();
    }

    function deleteRow(button) {
      const tbody = document.getElementById("items-tbody");
      // Evitar borrar el último renglón disponible
      if (tbody.rows.length <= 1) {
        alert("La cotización debe contener al menos un ítem.");
        return;
      }
      button.closest("tr").remove();
      calculateTotal();
    }

    function calculateTotal() {
      const tbody = document.getElementById("items-tbody");
      let grandTotal = 0;
      
      Array.from(tbody.rows).forEach(row => {
        const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
        const price = parseFloat(row.querySelector(".item-price").value) || 0;
        grandTotal += qty * price;
      });
      
      document.getElementById("total-amount").innerText = "$" + grandTotal.toFixed(2);
    }

    // ==========================================
    // LÓGICA DE COMUNICACIÓN CON LA API
    // ==========================================

    // Enviar mensaje al asistente
    async function sendChatMessage() {
      const input = document.getElementById("chat-input");
      const message = input.value.trim();
      const provider = document.getElementById("model-provider").value;
      const history = document.getElementById("chat-history");
      const btnSend = document.getElementById("btn-send");

      if (!message) return;

      // Deshabilitar UI temporalmente
      input.value = "";
      input.disabled = true;
      btnSend.disabled = true;

      // Imprimir burbuja de usuario
      const userBubble = document.createElement("div");
      userBubble.className = "message user";
      userBubble.innerText = message;
      history.appendChild(userBubble);
      history.scrollTop = history.scrollHeight;

      // Imprimir burbuja de cargando del agente
      const loadingBubble = document.createElement("div");
      loadingBubble.className = "message agent";
      loadingBubble.innerHTML = '<span class="loader"></span> Buscando respuesta...';
      history.appendChild(loadingBubble);
      history.scrollTop = history.scrollHeight;

      try {
        const response = await fetch("/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ message, provider })
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.error || "Fallo en la comunicación con el servidor.");
        }

        const data = await response.json();
        const replyText = data.response;

        // Renderizar la respuesta (procesando bloque <think> si es Qwen)
        let htmlResponse = "";
        let finalReply = replyText;
        const thinkMatch = replyText.match(/<think>([\\s\\S]*?)<\\/think>/);
        
        if (thinkMatch) {
          const thinkContent = thinkMatch[1].trim();
          finalReply = replyText.replace(/<think>[\\s\\S]*?<\\/think>/, "").trim();
          htmlResponse += \`
            <details class="thinking-block">
              <summary>Proceso de razonamiento (Qwen)</summary>
              <pre>\${thinkContent}</pre>
            </details>
          \`;
        }
        
        htmlResponse += \`<div>\${finalReply.replace(/\\n/g, "<br>")}</div>\`;
        loadingBubble.innerHTML = htmlResponse;

      } catch (error) {
        loadingBubble.className = "message agent";
        loadingBubble.style.borderColor = "#ef4444";
        loadingBubble.style.color = "#fca5a5";
        loadingBubble.innerText = "Error: " + error.message;
      } finally {
        input.disabled = false;
        btnSend.disabled = false;
        input.focus();
        history.scrollTop = history.scrollHeight;
      }
    }

    // Generar y descargar el reporte de cotizaciones en PDF
    async function generatePDFQuote() {
      const clientName = document.getElementById("client-name").value.trim();
      const clientEmail = document.getElementById("client-email").value.trim();
      const notes = document.getElementById("quote-notes").value.trim();
      const btnPdf = document.getElementById("btn-generate-pdf");
      const tbody = document.getElementById("items-tbody");

      if (!clientName || !clientEmail) {
        alert("Por favor, introduce el nombre y el correo del cliente.");
        return;
      }

      // Estructurar items
      const items = [];
      let itemsValidos = true;

      Array.from(tbody.rows).forEach(row => {
        const desc = row.querySelector(".item-desc").value.trim();
        const qty = parseInt(row.querySelector(".item-qty").value) || 0;
        const price = parseFloat(row.querySelector(".item-price").value) || 0;

        if (!desc) {
          itemsValidos = false;
        }
        items.push({ description: desc, quantity: qty, price: price });
      });

      if (!itemsValidos || items.length === 0) {
        alert("Por favor, escribe la descripción de todos los renglones.");
        return;
      }

      // Bloquear botón y mostrar spinner
      btnPdf.disabled = true;
      const originalText = btnPdf.innerHTML;
      btnPdf.innerHTML = '<span class="loader"></span> Generando archivo...';

      try {
        const response = await fetch("/quote", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ clientName, clientEmail, items, notes })
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.error || "Error al solicitar la compilación del PDF.");
        }

        // Descargar archivo binario
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = \`cotizacion_\${clientName.replace(/\\s+/g, "_")}.pdf\`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(downloadUrl);

      } catch (error) {
        alert("Error al generar la cotización: " + error.message);
      } finally {
        btnPdf.disabled = false;
        btnPdf.innerHTML = originalText;
      }
    }
  </script>
</body>
</html>
`;
