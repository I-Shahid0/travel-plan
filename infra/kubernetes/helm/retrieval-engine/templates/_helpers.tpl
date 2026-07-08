{{- define "retrieval-engine.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "retrieval-engine.fullname" -}}
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

{{- define "retrieval-engine.labels" -}}
helm.sh/chart: {{ include "retrieval-engine.name" . }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "retrieval-engine.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "retrieval-engine.selectorLabels" -}}
app.kubernetes.io/name: {{ include "retrieval-engine.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "retrieval-engine.image" -}}
{{- $registry := .Values.image.registry -}}
{{- $tag := .Values.image.tag | default "latest" -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .imageName $tag -}}
{{- else -}}
{{- printf "%s:%s" .imageName $tag -}}
{{- end -}}
{{- end }}

{{- define "retrieval-engine.postgresHost" -}}
{{- printf "%s-postgres" (include "retrieval-engine.fullname" .) }}
{{- end }}

{{- define "retrieval-engine.redisHost" -}}
{{- printf "%s-redis" (include "retrieval-engine.fullname" .) }}
{{- end }}

{{- define "retrieval-engine.otelEndpoint" -}}
{{- printf "http://%s-otel-collector:4317" (include "retrieval-engine.fullname" .) }}
{{- end }}

{{- define "retrieval-engine.envFrom" -}}
{{- if .Values.appEnv }}
          envFrom:
            - configMapRef:
                name: {{ include "retrieval-engine.fullname" . }}-env
{{- if .Values.appSecrets }}
            - secretRef:
                name: {{ include "retrieval-engine.fullname" . }}-env-secret
{{- end }}
{{- else if .Values.appSecrets }}
          envFrom:
            - secretRef:
                name: {{ include "retrieval-engine.fullname" . }}-env-secret
{{- end }}
{{- end }}
