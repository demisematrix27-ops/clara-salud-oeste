"use strict";

/*
  Dirección de la API FastAPI.
  Durante el desarrollo, FastAPI debe estar ejecutándose en:
  http://127.0.0.1:8000
*/
const API_URL = "https://clara-salud-oeste.onrender.com/";


// Elementos del HTML
const form = document.querySelector("#coverage-form" );
const identification = document.querySelector("#identification");
const symptoms = document.querySelector("#symptoms");
const planId = document.querySelector("#plan-id");
const submitButton = document.querySelector("#submit-button");

const initialView = document.querySelector("#initial-view");
const loadingView = document.querySelector("#loading-view");
const resultsView = document.querySelector("#results-view");

const statusMessage = document.querySelector("#status-message");
const resultsList = document.querySelector("#results-list");
const newConsultationButton = document.querySelector(
  "#new-consultation-button"
);

let isLoading = false;


// --------------------------------------------------
// Mostrar errores debajo de los campos
// --------------------------------------------------

function mostrarError(field, errorId, message) {
  const errorElement = document.querySelector(`#${errorId}`);

  if (!errorElement) {
    return;
  }

  errorElement.textContent = message;
  errorElement.hidden = !message;

  field.setAttribute(
    "aria-invalid",
    String(Boolean(message))
  );
}


// --------------------------------------------------
// Cargar los planes desde FastAPI
// --------------------------------------------------

async function cargarPlanes() {
  try {
    const response = await fetch(`${API_URL}/planes`);
    const planes = await response.json();

    if (!response.ok) {
      throw new Error(
        planes.detail || "No se pudieron cargar los planes."
      );
    }

    planId.innerHTML = "";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Selecciona una cobertura";

    planId.appendChild(defaultOption);

    planes.forEach((plan) => {
      const option = document.createElement("option");

      option.value = plan.id;

      option.textContent = plan.es_demo
        ? `${plan.nombre} - demostración`
        : plan.nombre;

      planId.appendChild(option);
    });

  } catch (error) {
    console.error("Error al cargar los planes:", error);

    planId.innerHTML = "";

    const errorOption = document.createElement("option");
    errorOption.value = "";
    errorOption.textContent = "No se pudieron cargar las coberturas";

    planId.appendChild(errorOption);

    statusMessage.textContent =
      "No se pudieron cargar los planes desde la API.";
  }
}


// --------------------------------------------------
// Validar el formulario
// --------------------------------------------------

function validarFormulario() {
  const identificationValue =
    identification.value.trim();

  const symptomsValue =
    symptoms.value.trim();

  const planValue =
    planId.value;

  const identificationError = identificationValue
    ? ""
    : "Ingresa una identificación para continuar.";

  const symptomsError = !symptomsValue
    ? "Describe tus síntomas para continuar."
    : symptomsValue.length < 15
      ? "Escribe al menos 15 caracteres."
      : "";

  const planError = planValue
    ? ""
    : "Selecciona un tipo de cobertura.";

  mostrarError(
    identification,
    "id-error",
    identificationError
  );

  mostrarError(
    symptoms,
    "symptoms-error",
    symptomsError
  );

  mostrarError(
    planId,
    "plan-error",
    planError
  );

  if (
    identificationError ||
    symptomsError ||
    planError
  ) {
    statusMessage.textContent =
      "Revisa los campos indicados para continuar.";

    if (identificationError) {
      identification.focus();
    } else if (symptomsError) {
      symptoms.focus();
    } else {
      planId.focus();
    }

    return false;
  }

  return true;
}


// --------------------------------------------------
// Enviar síntomas y plan a FastAPI
// --------------------------------------------------

async function consultarBackend() {
  const body = {
    sintomas: symptoms.value.trim(),
    plan_id: Number(planId.value)
  };

  const response = await fetch(
    `${API_URL}/recomendaciones-copago`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail || "No se pudo consultar la información."
    );
  }

  return data;
}



// --------------------------------------------------
// Crear tarjeta para una clínica
// --------------------------------------------------

function crearTarjetaClinica(clinica) {
  const card = document.createElement("article");

  card.className = "clinic-card";

  const title = document.createElement("h3");
  title.textContent = clinica.nombre;

  const location = document.createElement("p");
  location.textContent =
    `Ubicación: ${clinica.ubicacion || "No disponible"}`;

  const price = document.createElement("p");
  price.textContent =
    clinica.precio_consulta === null ||
    clinica.precio_consulta === undefined
      ? "Tarifa: No disponible"
      : `Tarifa: B/. ${Number(
          clinica.precio_consulta
        ).toFixed(2)}`;

  const copay = document.createElement("p");
  copay.textContent =
    clinica.copago_estimado === null ||
    clinica.copago_estimado === undefined
      ? "Copago estimado: No calculable"
      : `Copago estimado: B/. ${Number(
          clinica.copago_estimado
        ).toFixed(2)}`;

  card.appendChild(title);
  card.appendChild(location);
  card.appendChild(price);
  card.appendChild(copay);

  if (clinica.telefono) {
    const phone = document.createElement("p");
    phone.textContent =
      `Teléfono: ${clinica.telefono}`;
    card.appendChild(phone);
  }

  if (clinica.es_demo) {
    const warning = document.createElement("p");

    warning.className = "demo-warning";
    warning.textContent =
      "Datos de demostración. Confirma la tarifa y cobertura.";

    card.appendChild(warning);
  }

  if (clinica.relacion_confirmada === false) {
    const warning = document.createElement("p");

    warning.className = "network-warning";
    warning.textContent =
      "La relación con el plan aún no está confirmada.";

    card.appendChild(warning);
  }

  return card;
}



// --------------------------------------------------
// Mostrar resultados recibidos desde FastAPI
// --------------------------------------------------

function mostrarResultados(data) {
  const hospitalList = document.querySelector(
    "#hospital-list"
  );

  const suggestedSpecialty = document.querySelector(
    "#suggested-specialty"
  );

  const analysisSummary = document.querySelector(
    "#analysis-summary"
  );

  const resultsSubtitle = document.querySelector(
    "#results-subtitle"
  );

  hospitalList.innerHTML = "";

  const analisis = data.analisis || {};

  if (analisis.prioridad === "urgente") {
    suggestedSpecialty.textContent =
      "Atención inmediata";

    analysisSummary.textContent =
      analisis.mensaje ||
      "Busca atención médica inmediata.";

    resultsSubtitle.textContent =
      "Se detectaron posibles señales de alarma.";

    const alert = document.createElement("div");

    alert.className = "urgent-alert";
    alert.textContent =
      analisis.mensaje ||
      "Busca atención médica inmediata.";

    hospitalList.appendChild(alert);

    return;
  }

  suggestedSpecialty.textContent =
    data.especialidad ||
    analisis.especialidad_sugerida ||
    "Medicina general";

  analysisSummary.textContent =
    analisis.explicacion ||
    "La sugerencia es orientativa.";

  resultsSubtitle.textContent =
    `Fuente del análisis: ${
      analisis.fuente || "sistema"
    }`;

  if (
    !data.clinicas ||
    data.clinicas.length === 0
  ) {
    const empty = document.createElement("p");

    empty.textContent =
      "No hay clínicas registradas para esta especialidad y plan.";

    hospitalList.appendChild(empty);

    return;
  }

  data.clinicas.forEach((clinica) => {
    hospitalList.appendChild(
      crearTarjetaClinica(clinica)
    );
  });
}



// --------------------------------------------------
// Enviar el formulario
// --------------------------------------------------

form.addEventListener(
  "submit",
  async (event) => {
    event.preventDefault();

    if (!validarFormulario()) {
      return;
    }

    submitButton.disabled = true;
    initialView.hidden = true;
    loadingView.hidden = false;
    resultsView.hidden = true;

    statusMessage.textContent =
      "Analizando síntomas y consultando cobertura...";

    try {
      const data = await consultarBackend();

      mostrarResultados(data);

      loadingView.hidden = true;
      resultsView.hidden = false;

    } catch (error) {
      console.error(error);

      loadingView.hidden = true;
      resultsView.hidden = true;
      initialView.hidden = false;

      statusMessage.textContent =
        error.message ||
        "No se pudo completar la consulta.";

    } finally {
      submitButton.disabled = false;
    }
  }
);



// --------------------------------------------------
// Comenzar una nueva consulta
// --------------------------------------------------

if (newConsultationButton) {
  newConsultationButton.addEventListener(
    "click",
    () => {
      resultsView.hidden = true;
      loadingView.hidden = true;
      initialView.hidden = false;

      form.reset();
      statusMessage.textContent = "";
    }
  );
}




// --------------------------------------------------
// Cargar planes al abrir la página
// --------------------------------------------------

cargarPlanes();
