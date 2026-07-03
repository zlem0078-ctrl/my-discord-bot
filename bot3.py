import discord
import os
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread

# 1. Render 웹서버 설정 (안 잠들게 하는 코드)
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()


intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("슬래시 명령어가 성공적으로 등록되었습니다!")

bot = MyBot()

# ⚠️ [필수 수정] 관리자(유저님)의 디스코드 고유 ID(숫자)를 적어주세요.
# 디스코드 설정 -> 고급 -> 개발자 모드를 켠 뒤, 내 프로필을 우클릭해서 'ID 복사하기'를 하면 나옵니다.
ADMIN_ID = 1016337047679676426

# 유저들의 잔액 저장소
user_balances = {}

def get_balance(user_id: int) -> int:
    if user_id not in user_balances:
        user_balances[user_id] = 0
    return user_balances[user_id]


# 📥 관리자 DM에 들어갈 [승인 / 거절] 버튼 뷰
class AdminApprovalView(discord.ui.View):
    def __init__(self, requester_id: int, requester_name: str, amount: int, sender_name: str):
        super().__init__(timeout=None)
        self.requester_id = requester_id
        self.requester_name = requester_name
        self.amount = amount
        self.sender_name = sender_name

    # [승인] 버튼을 눌렀을 때
    @discord.ui.button(label="✅ 승인 (잔액 지급)", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 유저 잔액 추가
        if self.requester_id not in user_balances:
            user_balances[self.requester_id] = 0
        user_balances[self.requester_id] += self.amount

        # 관리자 DM 창 업데이트
        await interaction.response.edit_message(
            content=f"🟢 **충전 승인 완료**\n- 신청자: {self.requester_name}\n- 금액: {self.amount:,}원\n- 잔액이 정상 지급되었습니다.",
            view=None
        )

        # 신청한 유저에게 알림 DM 보내기 (또는 서버에서 알림)
        try:
            user = await bot.fetch_user(self.requester_id)
            await user.send(f"🪙 **충전 완료 알림**\n입금이 확인되어 **{self.amount:,}원**이 충전되었습니다!\n현재 잔액: **{get_balance(self.requester_id):,}원**")
        except:
            pass # 유저가 DM을 막아둔 경우 에러 방지

    # [거절] 버튼을 눌렀을 때
    @discord.ui.button(label="❌ 거절", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=f"🔴 **충전 거절 처리됨**\n- 신청자: {self.requester_name}\n- 금액: {self.amount:,}원",
            view=None
        )
        try:
            user = await bot.fetch_user(self.requester_id)
            await user.send(f"❌ **충전 취소 알림**\n신청하신 **{self.amount:,}원** 충전 요청이 거절되었습니다. 입금자명을 다시 확인해 주세요.")
        except:
            pass


# 2. 유저 충전 요청 모달 설정
class ChargeModal(discord.ui.Modal, title="💸 충전 요청"):
    amount = discord.ui.TextInput(label="금액(원)", placeholder="예: 10000", required=True)
    sender_name = discord.ui.TextInput(label="입금자명", placeholder="실제 입금하시는 분의 이름을 적어주세요.", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        bank_name = "농협은행"          
        account_number = "123-45-6789"  
        account_holder = "감준우"       

        try:
            charge_amount = int(self.amount.value)
        except ValueError:
            await interaction.response.send_message("❌ 금액에는 숫자만 입력해 주세요.", ephemeral=True)
            return

        # 🌟 관리자(유저님)에게 DM으로 승인 요청 보내기
        try:
            admin_user = await bot.fetch_user(ADMIN_ID)
            admin_embed = discord.Embed(title="🔔 새로운 충전 요청이 들어왔습니다.", color=discord.Color.orange())
            admin_embed.add_field(name="🙋‍♂️ 신청 유저", value=f"{interaction.user.name} ({interaction.user.mention})", inline=False)
            admin_embed.add_field(name="💰 신청 금액", value=f"{charge_amount:,}원", inline=True)
            admin_embed.add_field(name="👤 입금자명", value=self.sender_name.value, inline=True)
            
            # 버튼이 달린 뷰를 첨부해서 관리자에게 DM 발송
            await admin_user.send(
                embed=admin_embed, 
                view=AdminApprovalView(interaction.user.id, interaction.user.name, charge_amount, self.sender_name.value)
            )
        except Exception as e:
            print(f"관리자 DM 발송 실패 (ID를 잘못 적었거나 봇 DM이 차단됨): {e}")

        # 신청 유저 본인에게 계좌 안내 박스 출력 (이 시점엔 돈이 올라가지 않음)
        embed = discord.Embed(title="✅ 충전 신청이 접수되었습니다.", description="관리자가 입금 확인 후 잔액을 지급해 드립니다.", color=discord.Color.blue())
        embed.add_field(name="💰 신청 금액(원)", value=f"{charge_amount:,}원", inline=False)
        embed.add_field(name="👤 입금자명", value=self.sender_name.value, inline=False)
        embed.add_field(
            name="🏦 입금하실 계좌 정보 (받는 사람)", 
            value=f"**{bank_name}** `{account_number}`\n예금주: **{account_holder}**", 
            inline=False
        )
        embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# 3. 메뉴 버튼들이 들어갈 뷰(View) 설정
class MenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔋 충전", style=discord.ButtonStyle.primary, custom_id="charge_btn")
    async def charge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChargeModal())

    @discord.ui.button(label="📦 제품 목록", style=discord.ButtonStyle.secondary, custom_id="product_list_btn")
    async def product_list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="📦 제품 목록", color=discord.Color.brand_green())
        products = [
            "• 아시아서버 스킨 0-10개 | `30원` | 재고: **10개**",
            "• 아시아서버 스킨 11~20개 | `60원` | 재고: **0개**",
            "• 아시아서버 스킨 21~30개 | `100원` | 재고: **1개**",
            "• 아시아서버 스킨 31~40개 | `200원` | 재고: **24개**",
            "• 아시아서버 스킨 41~50개 | `420원` | 재고: **1개**",
            "• 아시아서버 스킨 51~80개 | `1000원` | 재고: **0개**",
            "• 아시아서버 스킨 81~100개 | `1400원` | 재고: **2개**",
            "• 아시아서버 스킨 101~150개 | `2400원` | 재고: **6개**",
            "• 아시아서버 스킨 151~200개 | `3200원` | 재고: **2개**",
            "• 아시아서버 스킨 200~250개 | `4200원` | 재고: **2개**",
            "• 아시아서버 스킨 250~300개 | `5200원` | 재고: **0개**",
            "• 아시아서버 스킨 300개이상 | `6200원` | 재고: **0개**",
        ]
        embed.description = "\n".join(products)
        embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="👤 프로필", style=discord.ButtonStyle.secondary, custom_id="profile_btn")
    async def profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        balance = get_balance(user.id)
        
        embed = discord.Embed(title=f"👤 {user.display_name}님의 프로필", color=discord.Color.gold())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="💳 보유 화폐", value=f"**{balance:,} 원**", inline=False)
        embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    print("-" * 30)
    print(f"봇 이름: {bot.user.name}")
    print("관리자 DM 승인 화폐 시스템 가동!")
    print("-" * 30)

@bot.tree.command(name="메뉴", description="충전, 제품 목록, 프로필 메뉴를 보여줍니다.")
async def show_menu(interaction: discord.Interaction):
    await interaction.response.send_message("아래 메뉴에서 원하시는 항목을 선택해주세요.", view=MenuView())

# ⚠️ 여기에 본인의 디스코드 봇 토큰을 정확히 넣어주세요
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)