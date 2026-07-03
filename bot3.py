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
        account_number = "1908-4450-1523"  
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


# 3-1. 제품 데이터
PRODUCTS = {
    "skin_0_10": {"name": "아시아서버 스킨 0-10개", "price": 30, "stock": 10},
    "skin_11_20": {"name": "아시아서버 스킨 11~20개", "price": 60, "stock": 0},
    "skin_21_30": {"name": "아시아서버 스킨 21~30개", "price": 100, "stock": 1},
    "skin_31_40": {"name": "아시아서버 스킨 31~40개", "price": 200, "stock": 24},
    "skin_41_50": {"name": "아시아서버 스킨 41~50개", "price": 420, "stock": 1},
    "skin_51_80": {"name": "아시아서버 스킨 51~80개", "price": 1000, "stock": 0},
    "skin_81_100": {"name": "아시아서버 스킨 81~100개", "price": 1400, "stock": 2},
    "skin_101_150": {"name": "아시아서버 스킨 101~150개", "price": 2400, "stock": 6},
    "skin_151_200": {"name": "아시아서버 스킨 151~200개", "price": 3200, "stock": 2},
    "skin_200_250": {"name": "아시아서버 스킨 200~250개", "price": 4200, "stock": 2},
    "skin_250_300": {"name": "아시아서버 스킨 250~300개", "price": 5200, "stock": 0},
    "skin_300_plus": {"name": "아시아서버 스킨 300개이상", "price": 6200, "stock": 0},
}

# 사용자 계정 데이터 (account_name: account_id 형식)
USER_ACCOUNTS = {
    "아시아서버 스킨 0-10개": "skin_0_10",
    "아시아서버 스킨 11~20개": "skin_11_20",
    "아시아서버 스킨 21~30개": "skin_21_30",
    "아시아서버 스킨 31~40개": "skin_31_40",
    "아시아서버 스킨 41~50개": "skin_41_50",
    "아시아서버 스킨 51~80개": "skin_51_80",
    "아시아서버 스킨 81~100개": "skin_81_100",
    "아시아서버 스킨 101~150개": "skin_101_150",
    "아시아서버 스킨 151~200개": "skin_151_200",
    "아시아서버 스킨 200~250개": "skin_200_250",
    "아시아서버 스킨 250~300개": "skin_250_300",
    "아시아서버 스킨 300개이상": "skin_300_plus",
}


# 3-2. 계정 선택 뷰
class PurchaseAccountSelectView(discord.ui.View):
    def __init__(self, user_id: int, product_id: str, product_name: str, product_price: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.product_id = product_id
        self.product_name = product_name
        self.product_price = product_price
        
        # Select 메뉴에 계정 추가
        self.add_item(self.create_account_select())
    
    def create_account_select(self):
        select = discord.ui.Select(
            placeholder="제공받을 계정을 선택해주세요",
            min_values=1,
            max_values=1
        )
        
        for account_name, account_id in USER_ACCOUNTS.items():
            select.add_option(label=account_name, value=account_id, emoji="📋")
        
        select.callback = self.account_selected
        return select
    
    async def account_selected(self, interaction: discord.Interaction):
        account_id = interaction.data['values'][0]
        account_name = next((k for k, v in USER_ACCOUNTS.items() if v == account_id), account_id)
        
        # 잔액 확인
        user_balance = get_balance(self.user_id)
        
        if user_balance < self.product_price:
            embed = discord.Embed(
                title="❌ 구매 실패",
                description="잔액이 부족합니다.",
                color=discord.Color.red()
            )
            embed.add_field(name="필요 잔액", value=f"{self.product_price:,}원", inline=True)
            embed.add_field(name="현재 잔액", value=f"{user_balance:,}원", inline=True)
            embed.add_field(name="부족액", value=f"{self.product_price - user_balance:,}원", inline=False)
            embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 잔액 차감
        user_balances[self.user_id] = user_balance - self.product_price
        new_balance = user_balances[self.user_id]
        
        # 구매 완료 메시지
        embed = discord.Embed(
            title="✅ 구매 완료",
            description=f"상품이 성공적으로 구매되었습니다!",
            color=discord.Color.green()
        )
        embed.add_field(name="📦 상품명", value=self.product_name, inline=False)
        embed.add_field(name="💰 가격", value=f"{self.product_price:,}원", inline=True)
        embed.add_field(name="📋 제공 계정", value=account_name, inline=True)
        embed.add_field(name="💳 현재 잔액", value=f"{new_balance:,}원", inline=False)
        embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# 3-3. 제품 선택 뷰
class PurchaseProductSelectView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        
        # Select 메뉴에 제품 추가
        self.add_item(self.create_product_select())
    
    def create_product_select(self):
        select = discord.ui.Select(
            placeholder="구매할 상품을 선택해주세요",
            min_values=1,
            max_values=1
        )
        
        for product_id, product_data in PRODUCTS.items():
            stock_status = "✅" if product_data['stock'] > 0 else "❌"
            select.add_option(
                label=f"{product_data['name']} - {product_data['price']:,}원",
                value=product_id,
                description=f"재고: {product_data['stock']}개 {stock_status}",
                emoji="🛍️"
            )
        
        select.callback = self.product_selected
        return select
    
    async def product_selected(self, interaction: discord.Interaction):
        product_id = interaction.data['values'][0]
        product_data = PRODUCTS[product_id]
        
        # 재고 확인
        if product_data['stock'] == 0:
            embed = discord.Embed(
                title="❌ 상품 품절",
                description=f"해당 상품은 현재 재고가 없습니다.",
                color=discord.Color.red()
            )
            embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 계정 선택으로 넘어가기
        embed = discord.Embed(
            title="📋 계정 선택",
            description="아래에서 제공받을 계정을 선택해주세요.",
            color=discord.Color.blue()
        )
        embed.add_field(name="📦 선택된 상품", value=product_data['name'], inline=False)
        embed.add_field(name="💰 가격", value=f"{product_data['price']:,}원", inline=False)
        embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
        
        await interaction.response.send_message(
            embed=embed,
            view=PurchaseAccountSelectView(self.user_id, product_id, product_data['name'], product_data['price']),
            ephemeral=True
        )


# 3-4. 메뉴 버튼들이 들어갈 뷰(View) 설정
class MenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔋 충전", style=discord.ButtonStyle.primary, custom_id="charge_btn")
    async def charge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChargeModal())

    @discord.ui.button(label="🛒 구매하기", style=discord.ButtonStyle.success, custom_id="purchase_btn")
    async def purchase_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_balance = get_balance(interaction.user.id)
        embed = discord.Embed(
            title="🛒 상품 구매",
            description="아래에서 구매할 상품을 선택해주세요.",
            color=discord.Color.blue()
        )
        embed.add_field(name="💳 현재 잔액", value=f"{user_balance:,}원", inline=False)
        embed.set_footer(text="이 메시지는 본인에게만 보입니다.")
        
        await interaction.response.send_message(
            embed=embed,
            view=PurchaseProductSelectView(interaction.user.id),
            ephemeral=True
        )

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
keep_alive()

# 2. 그다음 디스코드 봇을 로그인시킵니다.
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
