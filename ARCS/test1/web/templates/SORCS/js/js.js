// Token que Flask puso en la página. El servidor lo exige en cada escritura.
const TOKEN = document.querySelector('meta[name="arcs-token"]').content;
const mensaje = document.getElementById('mensaje');

function mostrar(texto, esError) {
	mensaje.textContent = texto;
	mensaje.className = esError ? 'error' : 'ok';
}

// 1) Al abrir la página, pedimos los términos y permisos al servidor y los dibujamos.
async function cargarTerminos() {
	const r = await fetch('/api/terminos');
	const datos = await r.json();

	const cont = document.getElementById('terminos');
	datos.parrafos.forEach(texto => {
		const p = document.createElement('p');
		p.textContent = texto;
		cont.appendChild(p);
	});

	const div = document.getElementById('permisos');
	datos.permisos.forEach(perm => {
		const label = document.createElement('label');
		const cb = document.createElement('input');
		cb.type = 'checkbox';
		cb.value = perm.id;
		cb.checked = perm.requerido || perm.por_defecto;
		label.appendChild(cb);
		label.append(' ' + perm.descripcion + (perm.requerido ? ' (obligatorio)' : ''));
		div.appendChild(label);
	});
}

// 2) Al enviar el formulario, mandamos el nombre y las respuestas al servidor.
document.getElementById('form').addEventListener('submit', async (e) => {
	e.preventDefault();

	const permisos = {};
	document.querySelectorAll('#permisos input').forEach(cb => {
		permisos[cb.value] = cb.checked;
	});

	const cuerpo = {
		nombre: document.getElementById('nombre').value.trim().toLowerCase(),
		aceptacion: {
			edad_confirmada: document.getElementById('edad').checked,
			permisos: permisos
		}
	};

	const r = await fetch('/api/cuenta', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-ARCS-Token': TOKEN },
		body: JSON.stringify(cuerpo)
	});
	const datos = await r.json();

	if (r.ok) {
		mostrar('Cuenta creada: ' + datos.cuenta + '. Ya puedes entrar a ARCS con ese nombre.', false);
	} else {
		mostrar(datos.error, true);
	}
});

// 3) Borrar cuenta (mismo esquema: token + confirmación).
document.getElementById('borrar').addEventListener('click', async () => {
	const nombre = document.getElementById('nombre_borrar').value.trim().toLowerCase();
	if (!document.getElementById('confirmo_borrar').checked) {
		mostrar('Marca la casilla para confirmar.', true);
		return;
	}
	const r = await fetch('/api/cuenta/' + encodeURIComponent(nombre), {
		method: 'DELETE',
		headers: { 'Content-Type': 'application/json', 'X-ARCS-Token': TOKEN },
		body: JSON.stringify({ confirmar: 'BORRAR' })
	});
	const datos = await r.json();

	if (r.ok) {
		mostrar('Cuenta ' + datos.borrada + ' borrada.', false);
	} else {
		mostrar(datos.error, true);
	}
});

cargarTerminos();

/*
Registro de cambios
Fecha/hora UTC: 2026-11-09 20:57
Versión del proyecto: no especificada
Modelo: GPT-6
Tiempo estimado de modificación: menos de 2 minutos
Detalles técnicos: JavaScript de carga de términos, permisos, creación y eliminación de cuentas; se conservó la lógica proporcionada.
Siguiente sesión: validar respuestas HTTP y manejo de errores de red/API.
*/