{{/*
Expand the name of the chart.
*/}}
{{- define "apptrack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "apptrack.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "apptrack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "apptrack.labels" -}}
helm.sh/chart: {{ include "apptrack.chart" . }}
{{ include "apptrack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "apptrack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "apptrack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service-specific labels
*/}}
{{- define "apptrack.serviceLabels" -}}
{{ include "apptrack.labels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Service-specific selector labels
*/}}
{{- define "apptrack.serviceSelectorLabels" -}}
{{ include "apptrack.selectorLabels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Create the image name for a service.
*/}}
{{- define "apptrack.image" -}}
{{- printf "%s/%s:%s" .Values.image.registry .service (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}
