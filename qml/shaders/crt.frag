#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    vec2 resolution;
    float curvature;
    float scanlineStrength;
    float noiseStrength;
    float chromaStrength;
} ubuf;

layout(binding = 1) uniform sampler2D source;

float hash21(vec2 point) {
    point = fract(point * vec2(123.34, 456.21));
    point += dot(point, point + 45.32);
    return fract(point.x * point.y);
}

void main() {
    vec2 centered = qt_TexCoord0 * 2.0 - 1.0;
    float radius2 = dot(centered, centered);
    vec2 warped = centered * (1.0 + ubuf.curvature * radius2);
    vec2 uv = warped * 0.5 + 0.5;

    float inside = step(0.0, uv.x) * step(uv.x, 1.0)
                 * step(0.0, uv.y) * step(uv.y, 1.0);
    vec2 pixel = 1.0 / max(ubuf.resolution, vec2(1.0));
    vec2 chroma = vec2(pixel.x * ubuf.chromaStrength * (0.35 + radius2), 0.0);

    vec4 middleSample = texture(source, clamp(uv, 0.0, 1.0));
    float red = texture(source, clamp(uv + chroma, 0.0, 1.0)).r;
    float green = middleSample.g;
    float blue = texture(source, clamp(uv - chroma, 0.0, 1.0)).b;
    vec3 color = vec3(red, green, blue);

    // Broad phosphor bars move from the top of the tube to the bottom.
    float rowPosition = uv.y * ubuf.resolution.y;
    float unevenSpacing = sin(rowPosition * 0.061) * 1.80
                        + sin(rowPosition * 0.017 + 1.4) * 3.20;
    float horizontalWobble = sin(uv.x * 10.0) * 1.30;
    float scanWave = 0.5 + 0.5 * sin(
        (rowPosition + unevenSpacing + horizontalWobble - ubuf.time * 45.0)
        * 0.39269908
    );
    color *= 1.0 + ubuf.scanlineStrength * scanWave;

    float rollPosition = fract(uv.y - ubuf.time * 0.11);
    float rollBand = exp(-pow((rollPosition - 0.5) * 11.0, 2.0));
    color *= 1.0 + rollBand * 0.055;

    float noise = hash21(
        floor(uv * ubuf.resolution) + floor(ubuf.time * 59.94)
    ) - 0.5;
    color += noise * ubuf.noiseStrength;

    vec2 edge = abs(centered);
    float vignette = 1.0 - 0.25 * smoothstep(0.65, 1.85, dot(edge, edge));
    float glassEdge = mix(
        0.70,
        1.0,
        smoothstep(0.0, 0.012, min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y)))
    );
    color *= vignette * glassEdge;

    fragColor = vec4(color * inside, middleSample.a * inside) * ubuf.qt_Opacity;
}
