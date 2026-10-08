$ErrorActionPreference = "Stop"

$models = @(
    @{
        Name = "face_landmarker.task"
        Url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    },
    @{
        Name = "hand_landmarker.task"
        Url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    }
)

foreach ($model in $models) {
    $path = Join-Path $PSScriptRoot $model.Name
    if (Test-Path $path) {
        Write-Host "$($model.Name) already exists - skipping."
        continue
    }

    Write-Host "Downloading $($model.Name)..."
    Invoke-WebRequest -Uri $model.Url -OutFile $path
    Write-Host "Saved: $path"
}

Write-Host "All MediaPipe models are ready."
