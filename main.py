# jihoo_impact.py
#
# pip install -U pillow
# python jihoo_impact.py
#
# output: jihoo-impact.webp

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import random

# ============================================================
# CONFIG
# ============================================================

NAME = "jihoo"

WIDTH = 800
HEIGHT = 320

FPS = 20
SECONDS = 4
TOTAL_FRAMES = FPS * SECONDS

OUTPUT = "jihoo-impact.webp"
WEBP_QUALITY = 75

BG = (13, 17, 23)

GREEN = (57, 211, 83)
LIGHT_GREEN = (126, 231, 135)

# 충돌/바닥 기준 위치
GROUND_Y = 245


# 글자를 얼마나 촘촘하게 파편으로 만들지
PARTICLE_STEP = 2
PARTICLE_RADIUS = 2

GRAVITY = 900

random.seed(42)


# ============================================================
# FONT
# 외부 폰트 필요 없음
# ============================================================

FONT = ImageFont.load_default(size=125)


# ============================================================
# NAME MASK
# ============================================================

mask = Image.new("L", (WIDTH, HEIGHT), 0)
mask_draw = ImageDraw.Draw(mask)

bbox = mask_draw.textbbox(
    (0, 0),
    NAME,
    font=FONT,
)

text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]

# 글자가 바닥에 닿았을 때의 위치
TARGET_X = (WIDTH - text_width) // 2
TARGET_Y = GROUND_Y - text_height - bbox[1] - 5

mask_draw.text(
    (TARGET_X, TARGET_Y),
    NAME,
    font=FONT,
    fill=255,
)


# ============================================================
# PARTICLE 생성
# ============================================================

particles = []

CENTER_X = WIDTH / 2

for y in range(0, HEIGHT, PARTICLE_STEP):
    for x in range(0, WIDTH, PARTICLE_STEP):

        if mask.getpixel((x, y)) <= 128:
            continue

        # 중심에서 얼마나 떨어져 있는가
        dx = x - CENTER_X

        # 충돌 시 바깥 방향으로 날아가게
        direction = 1 if dx >= 0 else -1

        # 중앙에 있는 입자도 랜덤하게 좌우로
        if abs(dx) < 30:
            direction = random.choice([-1, 1])

        vx = (
            direction * random.uniform(70, 260)
            + dx * random.uniform(0.4, 1.1)
        )

        # 위로 튀는 속도
        vy = -random.uniform(180, 520)

        particles.append({
            "x": x,
            "y": y,

            "vx": vx,
            "vy": vy,

            "bounce": random.uniform(0.25, 0.55),

            "delay": random.uniform(0, 0.07),

            "brightness": random.uniform(0.7, 1.0),
        })

print(f"Particles: {len(particles)}")



# ============================================================
# HELPERS
# ============================================================

def clamp(value):
    return max(0.0, min(1.0, value))


def ease_in_quad(t):
    t = clamp(t)
    return t * t


def ease_out_quad(t):
    t = clamp(t)
    return 1 - (1 - t) * (1 - t)


def mix_color(a, b, amount):

    amount = clamp(amount)

    return tuple(
        int(
            a[i]
            + (b[i] - a[i]) * amount
        )
        for i in range(3)
    )


# ============================================================
# TIMELINE
#
# 0.00 - 0.15 : 대기
# 0.15 - 0.38 : jihoo 낙하
# 0.38 - 0.43 : 충돌 + squash + flash
# 0.43 - 0.90 : 파편 physics
# 0.90 - 1.00 : fade
# ============================================================

IMPACT_TIME = 0.38



# ============================================================
# JIHOO 낙하
# ============================================================

def draw_falling_name(
    layer,
    t,
):

    draw = ImageDraw.Draw(layer)

    # 시작 위치
    start_y = -text_height - 30

    if t < 0.15:
        progress = 0

    else:
        progress = (
            t - 0.15
        ) / (
            IMPACT_TIME - 0.15
        )

    progress = ease_in_quad(progress)

    y = (
        start_y
        + (
            TARGET_Y - start_y
        )
        * progress
    )

    # --------------------------------------------
    # 충돌 직전에는 정상 글자
    # --------------------------------------------

    if t < IMPACT_TIME:

        draw.text(
            (
                TARGET_X,
                y,
            ),
            NAME,
            font=FONT,
            fill=GREEN + (255,),
        )

        return

    # --------------------------------------------
    # 충돌 직후 squash
    # --------------------------------------------

    squash_duration = 0.05

    age = t - IMPACT_TIME

    if age < squash_duration:

        amount = (
            age / squash_duration
        )

        # impact 순간 가장 납작했다가 사라짐
        squash = (
            0.65
            + amount * 0.35
        )

        temp = Image.new(
            "RGBA",
            (
                text_width + 20,
                text_height + 20,
            ),
            (0, 0, 0, 0),
        )

        temp_draw = ImageDraw.Draw(temp)

        temp_draw.text(
            (
                10 - bbox[0],
                10 - bbox[1],
            ),
            NAME,
            font=FONT,
            fill=GREEN + (
                int(
                    255
                    * (1 - amount)
                ),
            ),
        )

        new_height = max(
            1,
            int(
                temp.height
                * squash
            ),
        )

        temp = temp.resize(
            (
                temp.width,
                new_height,
            ),
            Image.Resampling.LANCZOS,
        )

        layer.alpha_composite(
            temp,
            (
                int(
                    CENTER_X
                    - temp.width / 2
                ),
                int(
                    GROUND_Y
                    - new_height
                ),
            ),
        )


# ============================================================
# PARTICLE PHYSICS
# ============================================================

def draw_particles(
    particle_layer,
    glow_layer,
    t,
):

    if t < IMPACT_TIME:
        return

    particle_draw = ImageDraw.Draw(
        particle_layer
    )

    glow_draw = ImageDraw.Draw(
        glow_layer
    )

    global_time = (
        t - IMPACT_TIME
    ) * SECONDS

    for p in particles:

        time = (
            global_time
            - p["delay"]
        )

        if time < 0:
            continue

        # --------------------------------------------
        # ballistic physics
        # --------------------------------------------

        x = (
            p["x"]
            + p["vx"] * time
        )

        y = (
            p["y"]
            + p["vy"] * time
            + 0.5
            * GRAVITY
            * time
            * time
        )

        # 순간 속도
        velocity_y = (
            p["vy"]
            + GRAVITY * time
        )

        # --------------------------------------------
        # 간단한 bounce simulation
        # --------------------------------------------

        floor = GROUND_Y - 2

        if y > floor:

            # 첫 충돌 시간을 근사해서
            # 반복적으로 튀는 느낌 생성
            bounce_time = (
                time
                - 0.35
            )

            if bounce_time > 0:

                bounce_phase = (
                    bounce_time * 5
                )

                bounce_height = (
                    45
                    * p["bounce"]
                    * math.exp(
                        -bounce_time * 2.4
                    )
                )

                y = (
                    floor
                    - abs(
                        math.sin(
                            bounce_phase
                            * math.pi
                        )
                    )
                    * bounce_height
                )

                # 마찰
                x = (
                    p["x"]
                    + p["vx"]
                    * (
                        0.35
                        + bounce_time * 0.35
                    )
                )

            else:
                y = floor

        # --------------------------------------------
        # Fade
        # --------------------------------------------

        fade_start = 1.7

        if global_time > fade_start:

            alpha = int(
                255
                * clamp(
                    1
                    - (
                        global_time
                        - fade_start
                    ) / 0.7
                )
            )

        else:
            alpha = 255

        if alpha <= 0:
            continue

        brightness = p["brightness"]

        color = (
            int(GREEN[0] * brightness),
            int(GREEN[1] * brightness),
            int(GREEN[2] * brightness),
            alpha,
        )

        r = PARTICLE_RADIUS

        particle_draw.ellipse(
            (
                x - r,
                y - r,
                x + r,
                y + r,
            ),
            fill=color,
        )

        # 일부 입자만 glow
        if p["brightness"] > 0.9:

            glow_draw.ellipse(
                (
                    x - 5,
                    y - 5,
                    x + 5,
                    y + 5,
                ),
                fill=(
                    LIGHT_GREEN[0],
                    LIGHT_GREEN[1],
                    LIGHT_GREEN[2],
                    int(alpha * 0.3),
                ),
            )


# ============================================================
# IMPACT FLASH
# ============================================================

def draw_impact_flash(
    layer,
    t,
):

    age = t - IMPACT_TIME

    if age < 0 or age > 0.15:
        return

    draw = ImageDraw.Draw(layer)

    progress = (
        age / 0.15
    )

    radius = (
        15
        + progress * 130
    )

    alpha = int(
        170
        * (1 - progress)
    )

    # 충돌 중심 glow
    draw.ellipse(
        (
            CENTER_X - radius,
            GROUND_Y - radius / 3,
            CENTER_X + radius,
            GROUND_Y + radius / 3,
        ),
        fill=(
            LIGHT_GREEN[0],
            LIGHT_GREEN[1],
            LIGHT_GREEN[2],
            alpha,
        ),
    )


# ============================================================
# RENDER FRAME
# ============================================================

def render(frame_index):

    t = (
        frame_index
        / TOTAL_FRAMES
    )

    base = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        BG + (255,),
    )


    # --------------------------------------------
    # name
    # --------------------------------------------

    name_layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    draw_falling_name(
        name_layer,
        t,
    )

    # --------------------------------------------
    # impact
    # --------------------------------------------

    impact_layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    draw_impact_flash(
        impact_layer,
        t,
    )

    impact_layer = impact_layer.filter(
        ImageFilter.GaussianBlur(12)
    )

    # --------------------------------------------
    # particles
    # --------------------------------------------

    particle_layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    glow_layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    draw_particles(
        particle_layer,
        glow_layer,
        t,
    )

    glow_layer = glow_layer.filter(
        ImageFilter.GaussianBlur(6)
    )

    # --------------------------------------------
    # composite
    # --------------------------------------------

    result = Image.alpha_composite(
        base,
        impact_layer,
    )

    result = Image.alpha_composite(
        result,
        glow_layer,
    )

    result = Image.alpha_composite(
        result,
        name_layer,
    )

    result = Image.alpha_composite(
        result,
        particle_layer,
    )

    return result.convert("RGB")


# ============================================================
# GENERATE
# ============================================================

print()
print("Generating JIHOO impact animation...")
print()

frames = []

for i in range(TOTAL_FRAMES):

    frames.append(
        render(i)
    )

    if i % FPS == 0:

        percent = int(
            i / TOTAL_FRAMES * 100
        )

        print(
            f"{percent}%"
        )


# ============================================================
# SAVE WEBP
# ============================================================

print()
print("Saving WebP...")

frames[0].save(
    OUTPUT,
    format="WEBP",
    save_all=True,
    append_images=frames[1:],
    duration=int(1000 / FPS),
    loop=0,
    quality=WEBP_QUALITY,
    method=6,
)

print()
print("────────────────────────────")
print("💥 DONE")
print(f"→ {OUTPUT}")
print(f"→ {WIDTH}x{HEIGHT}")
print(f"→ {FPS} FPS")
print("────────────────────────────")